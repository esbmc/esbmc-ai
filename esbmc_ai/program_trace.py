# Author: Yiannis Charalambous

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esbmc_ai.solution import SourceFile


@dataclass(kw_only=True)
class ProgramTrace:
    """Contains information about traces in source code."""

    trace_source: Literal["parser", "verifier"]
    """Is the trace from the parser or from the verifier?"""
    trace_index: int
    """The index position of this trace point in the trace stack."""
    source_file: "SourceFile"
    """The source file of this trace."""
    name: str | None = None
    """The name of the symbol, if applicable."""
    line_idx: int
    """The location of the trace."""
    comment: str | None = None
    """Used in instances like clang where it outputs per error a comment on what's wrong."""

    @property
    def filepath(self) -> Path:
        """The file path of the trace location."""
        return self.source_file.file_path
