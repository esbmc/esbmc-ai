# Author: Yiannis Charalambous

from pathlib import Path

from esbmc_ai.issue import Issue
from esbmc_ai.program_trace import ProgramTrace


class ClangOutputParser:
    """Parser for Clang/GCC diagnostic output format.

    Handles compilation errors and warnings in the standard format:
    <filename>:<line>:<col>: <error|warning|note>: <message>
    <source line>
    <indicator line (e.g., ^ pointing to error)>
    """

    @staticmethod
    def _parse_diagnostic_lines(output: str) -> list[tuple[str, int, str]]:
        """Extract diagnostic entries from compiler output.

        Args:
            output: Compiler output text containing diagnostics

        Returns:
            List of (filename, line_number, message) tuples for each error
        """
        output_split: list[str] = output.splitlines(True)

        # Find the first line not starting with "Parsing" (ESBMC-specific prefix)
        # Skip first 2 lines as they typically contain program header
        start_line: int = 2
        for idx, line in enumerate(output_split[start_line:], start=start_line):
            if not line.startswith("Parsing"):
                start_line = idx
                break

        diagnostics: list[tuple[str, int, str]] = []
        idx: int = start_line
        while idx < len(output_split):
            line = output_split[idx]
            line_split: list[str] = line.split(":")

            # Expected format: filename:line:col:type:message
            if len(line_split) == 5 and line_split[3].strip() == "error":
                filename: str = line_split[0]
                line_number: int = int(line_split[1])
                # col: int = int(line_split[2])  # Column not currently used
                message: str = line_split[4].strip()
                diagnostics.append((filename, line_number, message))

            # Skip 3 lines per diagnostic entry:
            # Line 1: "file:line:col: error: message"
            # Line 2: The actual source code line
            # Line 3: Error indicator (e.g., "^" or "~~~~~" pointing to error)
            idx += 3

        return diagnostics

    @staticmethod
    def parse_diagnostics(output: str) -> list[Issue]:
        """Parse Clang/GCC diagnostic format into Issue objects.

        Args:
            output: Compiler output text containing diagnostics

        Returns:
            List of Issue objects for each error found
        """
        issues: list[Issue] = []

        for filename, line_number, message in ClangOutputParser._parse_diagnostic_lines(
            output
        ):
            # Create a single-point trace for the compilation error
            trace: ProgramTrace = ProgramTrace(
                trace_index=0,
                path=Path(filename),
                line_idx=line_number - 1,  # Convert to 0-based indexing
            )

            issues.append(
                Issue(
                    error_type="Compilation Error",
                    message=message,
                    stack_trace=[trace],
                    severity="error",
                )
            )

        return issues
