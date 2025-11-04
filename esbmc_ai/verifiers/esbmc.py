# Author: Yiannis Charalambous

import signal
import re
from functools import cached_property
from time import perf_counter
from subprocess import PIPE, STDOUT, run, CompletedProcess
from pathlib import Path
from typing import NamedTuple
from typing_extensions import Any, override

from pydantic import BaseModel

from esbmc_ai.solution import Solution, SolutionIntegrityError

from esbmc_ai.verifier_output import VerifierOutput
from esbmc_ai.verifiers.base_source_verifier import BaseSourceVerifier
from esbmc_ai.verifiers.clang import ClangOutputParser
from esbmc_ai.program_trace import ProgramTrace
from esbmc_ai.issue import Issue, VerifierIssue

# Regex patterns for parsing ESBMC output
_STACK_TRACE_PATTERN = re.compile(
    r"\s+.+\s+at file ([^ ]+) line (\d+) column \d+ function ([^ ]+)"
)
_VIOLATED_PROPERTY_PATTERN = re.compile(
    r"Violated property:\s+file ([^ ]+) line (\d+) column \d+ function ([^ ]+)",
    re.DOTALL,
)
_TRACE_LINE_BASE_PATTERN = re.compile(
    r"State (\d+) file ([^ ]+) line (\d+)(?:.+) thread (\d+)\n[-]+\n?(.*)?", re.DOTALL
)
_TRACE_FUNCTION_PATTERN = re.compile(r" function ([^ ]+)")
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
    def _parse_issues(output: str) -> list[Issue]:
        """Parse ESBMC output and create Issue objects. Extracts all issues without filtering."""
        # Check for parsing/compilation errors - delegate to Clang parser
        if "ERROR: PARSING ERROR" in output:
            return ClangOutputParser.parse_diagnostics(output)

        # Check for verification failures (counterexamples)
        if "[Counterexample]" in output:
            return ESBMCOutputParser._parse_verification_failure(output)

        # No issues found
        return []

    @staticmethod
    def get_violated_property(output: str) -> str | None:
        """Extract the violated property line from ESBMC output.

        Args:
            output: Raw ESBMC output text

        Returns:
            Violated property text or None if not found
        """
        return ESBMCOutputParser._extract_violated_property_section(output)

    @staticmethod
    def _should_include_trace(trace: ProgramTrace, solution: Solution) -> bool:
        """Determine if a trace should be included based on solution files.

        Args:
            trace: The program trace to check
            solution: Solution object defining which files to include

        Returns:
            True if the trace's file exists in solution and is mapped
        """
        return (solution.base_dir / trace.path).exists() and str(
            trace.path
        ) in solution.files_mapped

    @staticmethod
    def filter_traces(esbmc_output: "ESBMCOutput", solution: Solution) -> "ESBMCOutput":
        """Filter traces in ESBMCOutput to only include files from the solution.

        Creates a new ESBMCOutput object with traces filtered to only include
        files that exist in the solution's base directory and are in files_mapped.

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
            if isinstance(issue, VerifierIssue):
                filtered_counterexample = [
                    trace
                    for trace in issue.counterexample
                    if ESBMCOutputParser._should_include_trace(trace, solution)
                ]
                # Create new VerifierIssue with filtered traces
                filtered_issues.append(
                    VerifierIssue(
                        error_type=issue.error_type,
                        message=issue.message,
                        stack_trace=filtered_stack_trace,
                        counterexample=filtered_counterexample,
                        severity=issue.severity,
                    )
                )
            else:
                # Create new Issue with filtered stack_trace
                filtered_issues.append(
                    Issue(
                        error_type=issue.error_type,
                        message=issue.message,
                        stack_trace=filtered_stack_trace,
                        severity=issue.severity,
                    )
                )

        # Return new ESBMCOutput with filtered issues
        return ESBMCOutput(
            return_code=esbmc_output.return_code,
            output=esbmc_output.output,
            issues=filtered_issues,
            duration=esbmc_output.duration,
        )

    @staticmethod
    def _parse_verification_failure(output: str) -> list[Issue]:
        """Parse verification failure with counterexample into VerifierIssue."""
        issues: list[Issue] = []

        # Extract error type from violated property
        error_type = ESBMCOutputParser._extract_error_type(output)
        if not error_type:
            error_type = "Unknown verification failure"

        # Extract error message (use violated property as message)
        violated_prop = ESBMCOutputParser._extract_violated_property_section(output)
        message = violated_prop or error_type

        # Parse stack trace (from --show-stacktrace output)
        stack_trace = ESBMCOutputParser._parse_stack_trace(output)

        # Parse counterexample traces
        counterexample = ESBMCOutputParser._parse_counterexample_traces(output)

        # If no explicit stack trace, use only the final counterexample element (error location)
        if not stack_trace and counterexample:
            stack_trace = [counterexample[-1]]

        if stack_trace:
            # Create VerifierIssue with separate stack_trace and counterexample
            issues.append(
                VerifierIssue(
                    error_type=error_type,
                    message=message,
                    stack_trace=stack_trace,
                    counterexample=counterexample,
                    severity="error",
                )
            )

        return issues

    @staticmethod
    def _extract_error_type(output: str) -> str | None:
        """Extract the error type (scenario) from violated property."""
        marker: str = "Violated property:\n"
        violated_property_index: int = output.rfind(marker)
        if violated_property_index == -1:
            return None

        violated_property_index += len(marker)
        from_loc_error_msg: str = output[violated_property_index:]

        # Find second new line which contains the scenario
        scenario_index: int = from_loc_error_msg.find("\n")
        if scenario_index == -1:
            return None

        scenario: str = from_loc_error_msg[scenario_index + 1 :]
        scenario_end_l_index: int = scenario.find("\n")
        scenario = scenario[:scenario_end_l_index].strip()

        return scenario if scenario else None

    @staticmethod
    def _parse_counterexample_traces(output: str) -> list[ProgramTrace]:
        """Parse counterexample section into ProgramTrace objects.

        Extracts ALL traces without filtering.
        """
        # Get [Counterexample] string idx
        try:
            ce_idx: int = output.index("[Counterexample]") + len("[Counterexample]")
        except ValueError:
            return []

        ce_idx_end: int = ce_idx
        traces: list[ProgramTrace] = []
        trace_idx: int = 0

        # Parse all state traces
        while True:
            # Check if done
            if output.find("State ", ce_idx) == -1:
                break

            ce_idx = output.index("State ", ce_idx)
            # Get the end of state block, which spans 3 lines:
            # Line 1: "State N file X line Y function Z thread T"
            # Line 2: "----" (separator)
            # Line 3: Error details or code line
            ce_idx_end = ce_idx
            ce_idx_end = output.index("\n", ce_idx_end) + 1
            ce_idx_end = output.index("\n", ce_idx_end) + 1
            ce_idx_end = output.index("\n", ce_idx_end) + 1

            # Parse the state line
            try:
                trace_results: ESBMCOutputParser._TraceResult | None = (
                    ESBMCOutputParser._parse_trace_line(output[ce_idx:ce_idx_end])
                )
            except ValueError:
                # Skip trace lines that cannot be parsed
                trace_results = None

            if trace_results:
                file_name: Path = trace_results.filename
                line_number: int = trace_results.line_number
                method_name: str = trace_results.method_name

                traces.append(
                    ProgramTrace(
                        trace_index=trace_idx,
                        path=Path(file_name),
                        line_idx=line_number - 1,  # Convert to 0-based
                        name=method_name if method_name else None,
                    )
                )

            ce_idx = ce_idx_end + 1
            trace_idx += 1

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
        # Find "Violated property:" string in ESBMC output
        lines: list[str] = output.splitlines()
        for ix, line in enumerate(lines):
            if "Violated property:" == line:
                return "\n".join(lines[ix : ix + 3])
        return None

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

        method_name: str | None = None
        error_line: str | None = None

        # Get elements that are always present
        match = _TRACE_LINE_BASE_PATTERN.search(line)
        if match:
            state_number: int | None = int(match.group(1)) if match.group(1) else None
            filename: str | None = match.group(2) if match.group(2) else None
            line_number: int | None = int(match.group(3)) if match.group(3) else None

            thread_index: int | None = int(match.group(4)) if match.group(4) else None

            # Don't return if any of the useful information is missing
            if any(x is None for x in [filename, line_number]):
                return None
            assert filename is not None and line_number is not None
        else:
            raise ValueError(f"Could not find a state match:\n{line}\n")

        # Optional elements - extract function name
        if " function " in line:
            match = _TRACE_FUNCTION_PATTERN.search(line)
            method_name = match.group(1) if match else None

        # If violated property is printed, don't get error line, it's not supported.
        if "Violated property:" not in line:
            match = _TRACE_ERROR_LINE_PATTERN.search(line)
            error_line = match.group(1) if match else None

        return ESBMCOutputParser._TraceResult(
            state_number=state_number or -1,
            filename=Path(filename),
            line_number=line_number,
            method_name=method_name or "",
            thread_index=thread_index or -1,
            error_line=error_line or "",
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
        try:
            # Find "Stack trace:" and extract indented lines after it
            lines = output.splitlines()
            stack_trace_idx = None
            for i, line in enumerate(lines):
                if line == "Stack trace:":
                    stack_trace_idx = i
                    break

            if stack_trace_idx is None:
                return None

            # Collect indented lines after "Stack trace:"
            indented_lines = []
            for line in lines[stack_trace_idx + 1 :]:
                if line and line[0].isspace():
                    indented_lines.append(line.strip())
                else:
                    # Stop at first non-indented line
                    break

            # Return the last indented line (the violated property message)
            return indented_lines[-1] if indented_lines else None
        except (ValueError, IndexError):
            return None

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
        try:
            # Find "Stack trace:" and extract indented lines after it
            lines = output.splitlines()
            stack_trace_idx = None
            for i, line in enumerate(lines):
                if line == "Stack trace:":
                    stack_trace_idx = i
                    break

            if stack_trace_idx is None:
                return None

            # Collect indented lines after "Stack trace:"
            indented_lines = []
            for line in lines[stack_trace_idx + 1 :]:
                if line and line[0].isspace():
                    indented_lines.append(line.strip())
                else:
                    # Stop at first non-indented line
                    break

            # Return all but the last line (which is the violated property message)
            if len(indented_lines) > 1:
                return "\n".join(indented_lines[:-1])
            else:
                return None
        except (ValueError, IndexError):
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
        entry_function: str = "main",
        params: list[str] | None = None,
    ) -> ESBMCOutput:
        esbmc_params: list[str] = params or self.global_config.verifier.esbmc.params
        timeout = timeout or self.global_config.verifier.esbmc.timeout

        if "--multi-property" in esbmc_params:
            raise ValueError(
                "Do not add --multi-property to ESBMC params, it is not yet supported!"
            )

        if "--input-file" in esbmc_params:
            raise ValueError("Do not add --input-file to ESBMC parameters.")

        if "--timeout" in esbmc_params:
            raise ValueError(
                "Do not add --timeout to ESBMC parameters, instead specify it in its own field."
            )

        if "--function" in esbmc_params:
            raise ValueError(
                "Don't add --function to ESBMC parameters, instead specify it in its own field."
            )

        if "--show-stacktrace" in esbmc_params:
            raise ValueError(
                "Don't add --show-stacktrace to ESBMC parameters, it is added automatically."
            )

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
        esbmc_cmd.extend("-I" + str(d) for d in solution.include_dirs.keys())

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

        # Run ESBMC from solution base_dir and get output
        process: CompletedProcess = run(
            esbmc_cmd,
            stdout=PIPE,
            stderr=STDOUT,
            cwd=solution.base_dir,
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
