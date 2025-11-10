# Author: Yiannis Charalambous

"""Parser for ESBMC --show-loops output and data structures for representing
ESBMC loop information."""

import re
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from esbmc_ai.solution import Solution


class ESBMCLoop(BaseModel):
    """Represents a single loop detected by ESBMC --show-loops."""

    loop_idx: int = Field(description="Loop index/ID from ESBMC.")
    file_name: Path = Field(description="Source file containing the loop.")
    line_number: int = Field(description="Line number where loop starts (1-based).")
    function_name: str = Field(description="Function containing the loop.")


class ESBMCLoops(BaseModel):
    """Collection of loops detected by ESBMC --show-loops."""

    loops: list[ESBMCLoop] = Field(
        default_factory=list, description="List of detected loops."
    )

    def filter_by_solution(self, solution: "Solution") -> "ESBMCLoops":
        """Filter loops to only include those from solution files."""
        solution_files = [f.abs_path for f in solution.files]
        filtered_loops = [
            loop
            for loop in self.loops
            if any(
                loop.file_name.is_relative_to(file_path)
                or file_path.is_relative_to(loop.file_name)
                or loop.file_name.name == file_path.name
                for file_path in solution_files
            )
        ]
        return ESBMCLoops(loops=filtered_loops)

    def __len__(self) -> int:
        """Return number of loops."""
        return len(self.loops)


class ESBMCLoopParser:
    """Parser for extracting loop information from ESBMC --show-loops output."""

    # Pattern: "goto-loop Loop N:"
    LOOP_HEADER_PATTERN = re.compile(r"goto-loop Loop (\d+):")

    # Pattern: " file <path> line <num> column <num> function <name>"
    LOOP_INFO_PATTERN = re.compile(
        r"\s+file\s+(.+?)\s+line\s+(\d+)\s+column\s+\d+\s+function\s+(\S+)"
    )

    @staticmethod
    def parse_loops(output: str) -> ESBMCLoops:
        """
        Parse ESBMC --show-loops output and return ESBMCLoops collection.

        Args:
            output: Raw output string from ESBMC with --show-loops flag

        Returns:
            ESBMCLoops object containing all detected loops
        """
        loops = ESBMCLoops()
        lines = output.split("\n")

        i = 0
        while i < len(lines):
            line = lines[i]

            # Check for loop header
            header_match = ESBMCLoopParser.LOOP_HEADER_PATTERN.search(line)
            if header_match:
                loop_idx = int(header_match.group(1))

                # Next line should contain loop information
                if i + 1 < len(lines):
                    info_line = lines[i + 1]
                    info_match = ESBMCLoopParser.LOOP_INFO_PATTERN.search(info_line)

                    if info_match:
                        file_path = Path(info_match.group(1))
                        line_number = int(info_match.group(2))
                        function_name = info_match.group(3)

                        loop = ESBMCLoop(
                            loop_idx=loop_idx,
                            file_name=file_path,
                            line_number=line_number,
                            function_name=function_name,
                        )
                        loops.loops.append(loop)

            i += 1

        return loops
