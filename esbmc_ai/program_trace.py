# Author: Yiannis Charalambous

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from esbmc_ai.solution import SourceFile


@dataclass
class ProgramTrace:
    """Contains information about traces in source code."""

    trace_type: Literal["function", "statement", "file"]
    """The scope of this trace."""
    trace_index: int
    """The index position of this trace point in the trace stack."""
    source_file: SourceFile
    """The source file of this trace."""
    name: str
    """The name of the symbol, if applicable."""
    line_idx: int
    """The location of the trace."""

    @property
    def filepath(self) -> Path:
        """The file path of the trace location."""
        return self.source_file.file_path
