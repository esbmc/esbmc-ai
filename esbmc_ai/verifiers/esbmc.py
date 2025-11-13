# Author: Yiannis Charalambous

import signal
import re
from functools import cached_property
from time import perf_counter
from subprocess import PIPE, STDOUT, run, CompletedProcess
from pathlib import Path
from typing import NamedTuple, cast
from typing_extensions import Any, override

from pydantic import BaseModel

from esbmc_ai.solution import Solution, SolutionIntegrityError

from esbmc_ai.verifier_output import VerifierOutput
from esbmc_ai.verifiers.base_source_verifier import BaseSourceVerifier
from esbmc_ai.verifiers.clang import ClangOutputParser
from esbmc_ai.program_trace import ProgramTrace, CounterexampleProgramTrace
from esbmc_ai.issue import Issue, VerifierIssue

# Regex patterns for parsing ESBMC output
_STACK_TRACE_PATTERN = re.compile(
    r"\s+.+\s+at file (\S+) line (\d+) column \d+ function (\S+)"
)
_VIOLATED_PROPERTY_PATTERN = re.compile(
    r"Violated property:\s+file (\S+) line (\d+) column \d+ function (\S+)",
    re.DOTALL,
)
_TRACE_LINE_BASE_PATTERN = re.compile(
    r"State (\d+) file (\S+) line (\d+)(?:.+) thread (\d+)\n[-]+\n?(.*)?", re.DOTALL
)
# Pattern for finding counterexample states in full text (non-greedy, stops at blank lines)
_COUNTEREXAMPLE_STATE_PATTERN = re.compile(
    r"State (\d+) file (\S+) line (\d+)(?:.+?) thread (\d+)\n[-]+\n(.*?)(?=\n\n|\nViolated|\Z)",
    re.DOTALL,
)
_TRACE_FUNCTION_PATTERN = re.compile(r" function (\S+)")
_TRACE_ERROR_LINE_PATTERN = re.compile(r"State (?:.+)\n[-]+\n?(.*)?", re.DOTALL)


class ESBMCOutputParser:
    """Parser for ESBMC-specific output text.

    Handles parsing of counterexamples, violated properties, and verification traces.
    Delegates compilation error parsing to ClangOutputParser.

    This is the single source of truth for all ESBMC output parsing and ESBMCOutput construction.
    """

    class _TraceResult(NamedTuple):
        """Internal data structure for parsed trace line information."""

        filename: Path
        line_number: int
        error_line: str
        state_number: int
        method_name: str
        thread_index: int

    @staticmethod
    def _extract_indented_lines_after(output: str, marker: str) -> list[str]:
        """Extract indented lines after a marker.

        This is a shared utility used by both ESBMCOutputParser and ESBMCOutputSections
        to parse sections of ESBMC output that follow the pattern:
            Marker:
              indented line 1
              indented line 2
              ...

        Args:
            output: The text to search
            marker: The marker line to find (exact match)

        Returns:
            List of indented lines (stripped) after the marker
        """
        lines = output.splitlines()
        for i, line in enumerate(lines):
            if line == marker:
                indented_lines = []
                for line in lines[i + 1 :]:
                    if line and line[0].isspace():
                        indented_lines.append(line.strip())
                    else:
                        break
                return indented_lines
        return []

    @staticmethod
    def parse_output(
        return_code: int,
        output: str,
        duration: float | None = None,
    ) -> "ESBMCOutput":
        """Parse ESBMC output and construct complete ESBMCOutput object.

        Extracts all issues and traces without filtering. The parser is pure -
        it only extracts structured data from text.

        Args:
            return_code: The exit code from ESBMC
            output: The raw output text from ESBMC
            duration: Execution time in seconds

        Returns:
            ESBMCOutput with all parsed issues and traces
        """
        issues = ESBMCOutputParser._parse_issues(output)
        return ESBMCOutput(
            return_code=return_code,
            output=output,
            issues=issues,
            duration=duration,
        )

    @staticmethod
    def _split_counterexample_sections(output: str) -> list[str]:
        """Split ESBMC output into individual counterexample sections."""
        parts = output.split("[Counterexample]")
        if len(parts) <= 1:
            return []
        return ["[Counterexample]" + part for part in parts[1:]]

    @staticmethod
    def _parse_issues(output: str) -> list[Issue]:
        """Parse ESBMC output and create Issue objects. Extracts all issues without filtering."""
        # Check for parsing/compilation errors - delegate to Clang parser
        if "ERROR: PARSING ERROR" in output:
            return ClangOutputParser.parse_diagnostics(output)

        # Check for verification failures (counterexamples)
        if "[Counterexample]" in output:
            counterexample_sections = ESBMCOutputParser._split_counterexample_sections(
                output
            )

            # Parse each counterexample section into an issue
            issues: list[Issue] = []
            for section in counterexample_sections:
                issue = ESBMCOutputParser._parse_verification_failure(section)
                if issue:
                    issues.append(issue)

            return issues

        # No issues found
        return []

    @staticmethod
    def _should_include_trace(trace: ProgramTrace, solution: Solution) -> bool:
        """Determine if a trace should be included based on solution files."""
        return (solution.working_dir / trace.path).exists() and trace.path in solution

    @staticmethod
    def filter_traces(esbmc_output: "ESBMCOutput", solution: Solution) -> "ESBMCOutput":
        """Filter traces in ESBMCOutput to only include files from the solution.

        Creates a new ESBMCOutput object with traces filtered to only include
        files that exist in the solution's base directory and are in the solution.

        Args:
            esbmc_output: The ESBMCOutput to filter
            solution: Solution object defining which files to include

        Returns:
            New ESBMCOutput with filtered traces in all issues
        """
        filtered_issues: list[Issue] = []

        for issue in esbmc_output.issues:
            # Filter stack_trace
            filtered_stack_trace = [
                trace
                for trace in issue.stack_trace
                if ESBMCOutputParser._should_include_trace(trace, solution)
            ]

            # Filter counterexample if it's a VerifierIssue
            new_issue: Issue
            if isinstance(issue, VerifierIssue):
                filtered_counterexample = [
                    trace
                    for trace in issue.counterexample
                    if ESBMCOutputParser._should_include_trace(trace, solution)
                ]
                # Create new VerifierIssue with filtered traces
                new_issue = issue.model_copy(
                    update={
                        "stack_trace": filtered_stack_trace,
                        "counterexample": filtered_counterexample,
                    },
                )
            else:
                # Create new Issue with filtered stack_trace
                new_issue = issue.model_copy(
                    update={"stack_trace": filtered_stack_trace}
                )
            filtered_issues.append(new_issue)

        # Return new ESBMCOutput with filtered issues
        return ESBMCOutput(
            return_code=esbmc_output.return_code,
            output=esbmc_output.output,
            issues=filtered_issues,
            duration=esbmc_output.duration,
        )

    @staticmethod
    def _parse_verification_failure(output: str) -> Issue | None:
        """Parse verification failure with counterexample into VerifierIssue."""
        # Extract both error type and message in one pass
        error_type, message = ESBMCOutputParser._extract_error_info(output)

        # Apply fallbacks if extraction failed
        if not error_type:
            error_type = "Unknown verification failure"

        if not message:
            # Fallback to violated property or error type
            violated_prop = ESBMCOutputParser._extract_violated_property_section(output)
            message = violated_prop or error_type

        # Parse stack trace (from --show-stacktrace output)
        stack_trace = ESBMCOutputParser._parse_stack_trace(output)

        # Parse counterexample traces
        counterexample = ESBMCOutputParser._parse_counterexample_traces(output)

        # If no explicit stack trace, use only the final counterexample element (error location)
        if not stack_trace and counterexample:
            stack_trace = [cast(ProgramTrace, counterexample[-1])]

        if stack_trace:
            # Create VerifierIssue with separate stack_trace and counterexample
            return VerifierIssue(
                error_type=error_type,
                message=message,
                stack_trace=stack_trace,
                counterexample=counterexample,
                severity="error",
            )

        return None

    @staticmethod
    def _extract_error_info(output: str) -> tuple[str | None, str | None]:
        """Extract both error type and message from Stack trace section.

        Returns error type (category) and message (details) from the error
        description lines. Parses once and extracts both pieces of information.

        Returns:
            Tuple of (error_type, error_message)

        Examples:
            "dereference failure: array bounds violated":
                ("dereference failure", "array bounds violated")
            "array bounds violated: array `dist' upper bound" + "(signed long int)i < 5":
                ("array bounds violated", "array `dist' upper bound: (signed long int)i < 5")
        """
        indented_lines = ESBMCOutputParser._extract_indented_lines_after(
            output, "Stack trace:"
        )

        if not indented_lines:
            return None, None

        # Collect all lines that don't start with "c:@" (error description lines)
        error_lines = [
            line.strip() for line in indented_lines if not line.startswith("c:@")
        ]

        if not error_lines:
            return None, None

        first_line = error_lines[0]

        # Split first line on colon to get type and start of message
        if ":" in first_line:
            parts = first_line.split(":", 1)
            error_type = parts[0].strip()

            # Build full message from remaining first line + additional lines
            message_parts = [parts[1].strip()] + error_lines[1:]
            error_message = ": ".join(part for part in message_parts if part)
        else:
            # No colon - use whole line as both type and message
            error_type = first_line
            error_message = first_line

        return error_type, error_message

    @staticmethod
    def _parse_counterexample_traces(output: str) -> list[CounterexampleProgramTrace]:
        """Parse counterexample section into CounterexampleProgramTrace objects.
        Extracts ALL traces without filtering.
        """
        # Find counterexample section
        try:
            ce_start = output.index("[Counterexample]")
        except ValueError:
            return []

        counterexample_section = output[ce_start:]
        traces: list[CounterexampleProgramTrace] = []

        # Use regex to find all state blocks in the counterexample
        for trace_idx, match in enumerate(
            _COUNTEREXAMPLE_STATE_PATTERN.finditer(counterexample_section)
        ):
            try:
                trace_results = ESBMCOutputParser._parse_trace_line(match.group(0))
            except ValueError:
                # Skip trace lines that cannot be parsed
                continue

            if trace_results:
                # Clean up the assignment string
                assignment = (
                    trace_results.error_line.strip()
                    if trace_results.error_line
                    else None
                )

                traces.append(
                    CounterexampleProgramTrace(
                        trace_index=trace_idx,
                        path=trace_results.filename,
                        line_idx=trace_results.line_number - 1,  # Convert to 0-based
                        name=(
                            trace_results.method_name
                            if trace_results.method_name
                            else None
                        ),
                        assignment=assignment,
                    )
                )

        return traces

    @staticmethod
    def _parse_stack_trace(output: str) -> list[ProgramTrace]:
        """Parse stack trace section from ESBMC output (--show-stacktrace).

        Extracts ALL traces without filtering.

        Expected format:
            Violated property:
              file <path> line <num> column <col> function <func>
            Stack trace:
              c:@F@function_name at file path.c line N column C function caller
              c:@F@main

        Returns:
            List of ProgramTrace objects representing the call stack,
            with the error location (from Violated property) as the final element
        """
        # Find "Stack trace:" marker
        try:
            stack_idx = output.index("Stack trace:")
        except ValueError:
            # No stack trace present (--show-stacktrace not used)
            return []

        # Find the end of the stack trace section (next blank line or end of counterexample)
        stack_start = stack_idx + len("Stack trace:\n")
        lines = output[stack_start:].split("\n")

        traces: list[ProgramTrace] = []
        trace_idx = 0

        # Pattern to match stack trace lines with file information
        # Format: "  symbol at file <path> line <num> column <col> function <func>"
        for line in lines:
            # Stop at blank line or end of section
            if not line.strip():
                break

            # Try to parse the line
            match = _STACK_TRACE_PATTERN.search(line)
            if match:
                file_path = Path(match.group(1))
                line_number = int(match.group(2))
                function_name = match.group(3)

                traces.append(
                    ProgramTrace(
                        trace_index=trace_idx,
                        path=file_path,
                        line_idx=line_number - 1,  # Convert to 0-based
                        name=function_name,
                    )
                )
                trace_idx += 1

        # Extract error location from "Violated property:" line and add as final trace
        # Format: "  file <path> line <num> column <col> function <func>"
        match = _VIOLATED_PROPERTY_PATTERN.search(output[:stack_idx])
        if match:
            file_path = Path(match.group(1))
            line_number = int(match.group(2))
            function_name = match.group(3)

            traces.append(
                ProgramTrace(
                    trace_index=trace_idx,
                    path=file_path,
                    line_idx=line_number - 1,  # Convert to 0-based
                    name=function_name,
                )
            )

        return traces

    @staticmethod
    def _extract_violated_property_section(output: str) -> str | None:
        """Gets the violated property line from ESBMC output string."""
        indented_lines = ESBMCOutputParser._extract_indented_lines_after(
            output, "Violated property:"
        )
        # Return the first indented line (the file/line/function info)
        return indented_lines[0] if indented_lines else None

    @staticmethod
    def _parse_trace_line(
        line: str,
    ) -> "ESBMCOutputParser._TraceResult | None":
        """Parses a trace line from ESBMC counterexample output.

        Expected format (3 lines):
        State <N> file <filename> line <N> [function <name>] thread <N>
        ----
        [error details or code line]

        Returns:
            _TraceResult containing parsed information, or None if critical fields missing
        Raises:
            ValueError if the line doesn't match the expected format
        """
        # Get elements that are always present
        match = _TRACE_LINE_BASE_PATTERN.search(line)
        if not match:
            raise ValueError(f"Could not find a state match:\n{line}\n")

        # Extract base groups
        filename = match.group(2)
        line_number_str = match.group(3)

        # Critical fields must be present
        if not filename or not line_number_str:
            return None

        state_number = int(match.group(1)) if match.group(1) else -1
        line_number = int(line_number_str)
        thread_index = int(match.group(4)) if match.group(4) else -1

        # Optional elements - extract function name
        method_name = ""
        if " function " in line:
            func_match = _TRACE_FUNCTION_PATTERN.search(line)
            if func_match:
                method_name = func_match.group(1)

        # Extract error line if not a violated property
        error_line = ""
        if "Violated property:" not in line:
            error_match = _TRACE_ERROR_LINE_PATTERN.search(line)
            if error_match:
                error_line = error_match.group(1) or ""

        return ESBMCOutputParser._TraceResult(
            state_number=state_number,
            filename=Path(filename),
            line_number=line_number,
            method_name=method_name,
            thread_index=thread_index,
            error_line=error_line,
        )


class ESBMCOutputSections(BaseModel):
    """Provides access to raw text sections of ESBMC output.

    This class parses and caches specific sections of the raw ESBMC output
    for efficient access without reparsing.
    """

    model_config = {"frozen": True}

    violated_property: str | None
    """Raw violated property message (last line of Stack trace section)."""
    counterexample: str | None
    """Raw counterexample section from [Counterexample] marker to end."""
    stack_trace: str | None
    """Raw stack trace lines (without header, excluding violated property message)."""

    @staticmethod
    def from_output(output: str) -> "ESBMCOutputSections":
        """Parse ESBMC output and extract all sections.

        Args:
            output: The raw output text from ESBMC

        Returns:
            ESBMCOutputSections with parsed and cached sections
        """
        return ESBMCOutputSections(
            violated_property=ESBMCOutputSections._parse_violated_property(output),
            counterexample=ESBMCOutputSections._parse_counterexample(output),
            stack_trace=ESBMCOutputSections._parse_stack_trace(output),
        )

    @staticmethod
    def _parse_violated_property(output: str) -> str | None:
        """Extract violated property message from output."""
        indented_lines = ESBMCOutputParser._extract_indented_lines_after(
            output, "Stack trace:"
        )
        # Return the last indented line (the violated property message)
        return indented_lines[-1] if indented_lines else None

    @staticmethod
    def _parse_counterexample(output: str) -> str | None:
        """Extract counterexample section from output."""
        try:
            start = output.index("[Counterexample]")
            return output[start:]
        except ValueError:
            return None

    @staticmethod
    def _parse_stack_trace(output: str) -> str | None:
        """Extract stack trace lines from output."""
        indented_lines = ESBMCOutputParser._extract_indented_lines_after(
            output, "Stack trace:"
        )
        # Return all but the last line (which is the violated property message)
        if len(indented_lines) > 1:
            return "\n".join(indented_lines[:-1])
        return None


class ESBMCOutput(VerifierOutput):
    """Pure data model for ESBMC verification output.

    Use ESBMCOutputParser to construct instances from raw ESBMC output.
    """

    @property
    @override
    def successful(self) -> bool:
        return self.return_code == 0

    @cached_property
    def sections(self) -> ESBMCOutputSections:
        """Access raw text sections of the ESBMC output.

        Returns:
            ESBMCOutputSections object providing access to raw parts of the output.
        """
        return ESBMCOutputSections.from_output(self.output)


class ESBMC(BaseSourceVerifier):
    """Verifier class that uses ESBMC."""

    FORBIDDEN_PARAMS = {
        "--multi-property": "it is not yet supported!",
        "--input-file": "",
        "--timeout": "instead specify it in its own field.",
        "--function": "instead specify it in its own field.",
        "--show-stacktrace": "it is added automatically.",
    }

    def __init__(self) -> None:
        super().__init__(verifier_name="esbmc", authors="")

    @property
    def esbmc_path(self) -> Path:
        """Returns the ESBMC path from config."""
        if not self.global_config.verifier.esbmc.path:
            raise ValueError("No esbmc path set.")
        return self.global_config.verifier.esbmc.path.absolute()

    @override
    def verify_source(
        self,
        *,
        solution: Solution,
        timeout: int | None = None,
        entry_function: str | None = None,
        params: list[str] | None = None,
    ) -> ESBMCOutput:
        timeout = timeout or self.global_config.verifier.esbmc.timeout
        entry_function = entry_function or self.global_config.solution.entry_function
        esbmc_params: list[str] = params or self.global_config.verifier.esbmc.params

        # Validate forbidden parameters
        for param, reason in self.FORBIDDEN_PARAMS.items():
            if param in esbmc_params:
                msg = f"Do not add {param} to ESBMC parameters"
                if reason:
                    msg += f", {reason}"
                else:
                    msg += "."
                raise ValueError(msg)

        # Verify source is not responsible for saving the solution.
        if not solution.verify_solution_integrity():
            raise SolutionIntegrityError(solution.files)

        # Check if cached version exists.
        enable_cache: bool = self.global_config.verifier.enable_cache
        cache_properties: Any = [solution, entry_function, timeout, params]
        if enable_cache:
            cached_result: Any = self._load_cached(cache_properties)
            if cached_result is not None:
                return cached_result

        # Call ESBMC to temporary folder.
        return_code, output, duration = self._esbmc(
            solution=solution,
            esbmc_params=esbmc_params,
            entry_function=entry_function,
            timeout=timeout,
        )

        # Parse output and construct result
        result: ESBMCOutput = ESBMCOutputParser.parse_output(
            return_code=return_code,
            output=output,
            duration=duration,
        )

        # Filter traces to only include files from the solution
        result = ESBMCOutputParser.filter_traces(result, solution)

        self.logger.debug(f"Verification Successful: {result.successful}")
        self.logger.debug(f"ESBMC Exit Code: {return_code}")
        self.logger.debug(f"ESBMC Output: {output}")

        if enable_cache:
            self._save_cached(cache_properties, result)

        return result

    def _esbmc(
        self,
        solution: Solution,
        esbmc_params: list[str],
        entry_function: str,
        timeout: int | None = None,
    ) -> tuple[int, str, float]:
        """Exit code will be 0 if verification successful, 1 if verification
        failed. And any other number for compilation error/general errors.

        Returns:
            Tuple of (return_code, output, duration_seconds)
        """

        # Build parameters list
        esbmc_cmd = [str(self.esbmc_path)] + esbmc_params
        # Source code files (only accept valid ones)
        esbmc_cmd.append("--input-file")
        esbmc_cmd.extend(
            str(file.file_path) for file in solution.get_files_by_ext(["c", "cpp"])
        )
        # Header files/dir
        esbmc_cmd.extend("-I" + str(d) for d in solution.include_dirs)

        # Add timeout suffix for parameter.
        if timeout:
            esbmc_cmd.extend(["--timeout", str(timeout) + "s"])
        # Add entry function for parameter.
        esbmc_cmd.extend(["--function", entry_function])
        # Add stack trace output (always enabled)
        esbmc_cmd.append("--show-stacktrace")

        self._logger.info("Running ESBMC: " + " ".join(esbmc_cmd))

        # Add slack time to process to allow verifier to timeout and end gracefully.
        process_timeout: float | None = timeout + 5 if timeout else None

        # Measure execution time
        start_time = perf_counter()

        # Run ESBMC from solution working_dir and get output
        process: CompletedProcess = run(
            esbmc_cmd,
            stdout=PIPE,
            stderr=STDOUT,
            cwd=solution.working_dir,
            timeout=process_timeout,
            check=False,
        )

        duration = perf_counter() - start_time

        # Check segfault.
        if process.returncode == -signal.SIGSEGV:
            raise RuntimeError(
                "ESBMC has segfaulted. Please report the issue "
                "to developers: https://www.github.com/esbmc/esbmc/issues"
            )

        output: str = process.stdout.decode("utf-8")
        return process.returncode, output, duration
