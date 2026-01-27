# Author: Yiannis Charalambous

from collections import defaultdict
import re
from dataclasses import dataclass
from subprocess import CompletedProcess
from typing import DefaultDict, Literal, cast, override
from pathlib import Path
from pydantic import Field

from esbmc_ai.issue import Issue
from esbmc_ai.solution import Solution
from esbmc_ai.program_trace import ProgramTrace
from esbmc_ai.verifier_output import VerifierOutput
from esbmc_ai.verifiers import BaseSourceVerifier


class CommandOracleVerifierOutput(VerifierOutput):
    """
    Provides raw output, the issue will be 1 if successful is false.
    """

    exit_success: int = Field(default=0)

    @property
    @override
    def successful(self) -> bool:
        return self.return_code == self.exit_success


@dataclass
class StackTraceRegexSpec:
    """
    Regex specification for parsing stack traces within an issue.

    The hierarchy is:
    1. `block` - Selects the entire stack trace block from within an issue
    2. `trace_entry` - Matches individual trace entries within the block
    3. Individual field patterns extract properties from each trace entry
    """

    block: str
    """Regex pattern to select the entire stack trace block within an issue."""
    trace_entry: str
    """Regex pattern to match individual trace entries within the block.
    Each entry may span multiple lines (e.g., GCC shows source snippets)."""
    trace_index: str
    """Regex pattern to extract the trace position/index from a trace entry."""
    path: str
    """Regex pattern to extract the file path from a trace entry."""
    name: str
    """Regex pattern to extract the function/symbol name from a trace entry."""
    line_index: str
    """Regex pattern to extract the line number from a trace entry."""


@dataclass
class IssueRegexSpec:
    """
    Regex specification for parsing individual issues from verifier output.

    The hierarchy is:
    1. `block` - Selects individual issue blocks from the entire output
    2. Individual field patterns extract properties from within each issue block
    3. `stack_trace_spec` - Nested spec for parsing stack traces within the issue
    """

    block: str
    """Regex pattern to select individual issue blocks from the verifier output."""
    error_type: str
    """Regex pattern to extract the error type (e.g., 'TypeError', 'AssertionError')."""
    message: str
    """Regex pattern to extract the error message/description."""
    stack_trace_spec: StackTraceRegexSpec
    """Nested specification for parsing the stack trace within this issue."""
    severity: str
    """Regex pattern to extract the severity level (e.g., 'error', 'warning', 'info')."""


pytest_spec: IssueRegexSpec = IssueRegexSpec(
    # Match both collection ERROR blocks and test FAILURE blocks
    # Test failure: "_____ test_name _____" (underscores, space, identifier, space, underscores)
    # Collection error: "_____ ERROR collecting path _____"
    # Block ends at next block header, pytest-regtest report, short test summary, or end of string
    # Note: Use \Z instead of $ to match only end of string (not end of line in MULTILINE mode)
    block=r"_{5,}\s+(?:ERROR collecting [^\n]+|\w+)\s+_{5,}\n.*?(?=_{5,}\s+(?:ERROR|\w+)\s+_{5,}|-{5,}\s+pytest-regtest|={5,}\s+short test summary|\Z)",
    # Extract error type from lines like "E   SyntaxError: invalid syntax" or "E   AssertionError"
    error_type=r"E\s+(\w+Error)",
    # Extract the error message after the error type (handles both "Error: msg" and "Error" alone)
    message=r"E\s+\w+Error:?\s*(.+?)$",
    # Severity is always "error" for pytest issues (collection errors and test failures)
    severity=r"(ERROR|FAILED)",
    stack_trace_spec=StackTraceRegexSpec(
        # Match all location lines: "path.py:line: in func" or "path.py:line: ErrorType"
        block=r"(?:^[^\s>E].+?\.py:\d+:.*$\n?)+",
        # Each trace entry is a single line in pytest (e.g., "tests/test_config.py:6: in <module>")
        trace_entry=r"^[^\s>E].+?\.py:\d+:.*$",
        # Individual trace index is implicit in pytest (order in stack)
        trace_index=r"^",  # Not applicable for pytest, using placeholder
        # Extract file path from lines like "tests/test_config.py:6: in <module>"
        path=r"([^\s:]+\.py):\d+:",
        # Extract function name from "in func_name" (may not exist in test failures)
        name=r":\s+in\s+(.+?)$",
        # Extract line number from lines like "tests/test_config.py:6:"
        line_index=r":(\d+):",
    ),
)


class CommandOracleOutputParser:
    """
    Oracle output parser using regex. Defines the following regex field hierarchy:
    * Issue start
    * Issue severity, issue error type, issue message, issue stack trace

    Need to figure out correct way to express this...
    """

    def __init__(self, regex_spec: IssueRegexSpec) -> None:
        self.regex_spec: IssueRegexSpec = regex_spec

    @staticmethod
    def spec_from_solution(solution: Solution) -> IssueRegexSpec | None:
        """
        Uses statistics to infer what language this solution is to get the
        best available parser or None.
        """

        lang_map: DefaultDict[str, int] = defaultdict(int)
        highest: str = ""

        # Count
        for f in solution.files:
            lang_map[f.file_extension] += 1
            if not highest:
                highest = f.file_extension
            elif lang_map[highest] < lang_map[f.file_extension]:
                highest = f.file_extension

        match highest:
            case ".py":
                return pytest_spec
            case _:
                return None

    def parse_output(
        self, exit_success: int, return_code: int, duration: float, output: str
    ) -> CommandOracleVerifierOutput:
        # Extract all issue blocks from the output
        issue_blocks: list[str] = []
        for match in re.finditer(
            self.regex_spec.block, output, re.DOTALL | re.MULTILINE
        ):
            issue_blocks.append(match.group(0))

        # Parse each issue block to extract individual issues
        issues: list[Issue] = [self._parse_issue(block) for block in issue_blocks]

        return CommandOracleVerifierOutput(
            exit_success=exit_success,
            return_code=return_code,
            issues=issues,
            output=output,
            duration=duration,
        )

    def _parse_issue(self, issue_text: str) -> Issue:
        """Function that parses a single issue and returns it."""

        # Extract error type
        error_type_match = re.search(
            self.regex_spec.error_type, issue_text, re.MULTILINE
        )
        error_type = error_type_match.group(1) if error_type_match else "Unknown"

        # Extract message
        message_match = re.search(self.regex_spec.message, issue_text, re.MULTILINE)
        message = message_match.group(1) if message_match else ""

        # Extract severity
        severity_match = re.search(self.regex_spec.severity, issue_text, re.MULTILINE)
        severity_str = severity_match.group(1).lower() if severity_match else "error"
        # Convert to valid severity literal
        if severity_str not in ["error", "warning", "info"]:
            severity_str = "error"
        # Type cast after validation
        severity: Literal["error", "warning", "info"] = cast(
            Literal["error", "warning", "info"], severity_str
        )

        # Extract stack trace
        stack_trace_spec: StackTraceRegexSpec = self.regex_spec.stack_trace_spec
        stack_trace_block_match = re.search(
            stack_trace_spec.block, issue_text, re.MULTILINE
        )

        stack_trace: list[ProgramTrace] = []
        if stack_trace_block_match:
            stack_trace_block = stack_trace_block_match.group(0)

            # Find individual trace entries using trace_entry pattern
            # This properly handles multi-line trace entries (e.g., GCC with source snippets)
            for trace_index, entry_match in enumerate(
                re.finditer(
                    stack_trace_spec.trace_entry, stack_trace_block, re.MULTILINE
                )
            ):
                entry_text = entry_match.group(0)

                # Extract path
                path_match = re.search(stack_trace_spec.path, entry_text)
                # Extract name
                name_match = re.search(stack_trace_spec.name, entry_text)
                # Extract line index
                line_idx_match = re.search(stack_trace_spec.line_index, entry_text)

                if path_match and line_idx_match:
                    path = Path(path_match.group(1))
                    name = name_match.group(1) if name_match else None
                    line_idx = int(line_idx_match.group(1)) - 1  # Convert to 0-based

                    stack_trace.append(
                        ProgramTrace(
                            trace_index=trace_index,
                            path=path,
                            name=name,
                            line_idx=line_idx,
                        )
                    )

        # Ensure at least one trace point exists
        if not stack_trace:
            # Create a dummy trace point if none were found
            stack_trace.append(
                ProgramTrace(
                    trace_index=0,
                    path=Path("unknown"),
                    name=None,
                    line_idx=0,
                )
            )

        return Issue(
            error_type=error_type,
            message=message,
            stack_trace=stack_trace,
            severity=severity,
        )


class CommandOracle(BaseSourceVerifier):
    """
    Provides a generic verifier that works by repeatedly running a command.
    Does not provide advanced output parsing capabilities.
    """

    def __init__(self) -> None:
        super().__init__(verifier_name="command-oracle", authors="")

    def _cmd_formatted(self, solution: Solution) -> str:
        """Formats and returns the cmd to use."""

        cmd: str = self._global_config.verifier.command_oracle.cmd
        cmd.format(
            files=[f.file_path for f in solution.files],
            # TODO In the future add another config field for customizing each
            # include dir manually with a default value of -I{p}.
            includes=" ".join([f"-I{p}" for p in solution.include_dirs]),
        )
        return cmd

    @override
    def verify_source(
        self,
        *,
        solution: Solution,
        timeout: int | None = None,
    ) -> VerifierOutput:

        # Build the variables: {files} and {ifiles}
        cmd: str = self._cmd_formatted(solution)

        result: CompletedProcess
        duration: float
        result, duration = self.run_command(
            cmd=cmd.split(" "),
            cwd=solution.working_dir,
            process_timeout=timeout,
        )

        spec: IssueRegexSpec | None = CommandOracleOutputParser.spec_from_solution(
            solution
        )

        if not spec:
            raise ValueError(
                "Could not infer spec from solution. No builtin spec exists. "
                "Please configure manually..."
            )

        return CommandOracleOutputParser(spec).parse_output(
            exit_success=self._global_config.verifier.command_oracle.exit_success,
            return_code=result.returncode,
            output=result.stdout.decode("utf-8"),
            duration=duration,
        )
