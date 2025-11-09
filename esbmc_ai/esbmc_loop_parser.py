"""Parser for ESBMC --show-loops output."""

import re
from pathlib import Path

from esbmc_ai.esbmc_loops import ESBMCLoop, ESBMCLoops


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
