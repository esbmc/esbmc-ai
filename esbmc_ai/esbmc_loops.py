"""Data structures for representing ESBMC loop information."""

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
