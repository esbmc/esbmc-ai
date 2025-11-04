# Author: Yiannis Charalambous

from pathlib import Path
from pydantic import BaseModel, Field


class ProgramTrace(BaseModel):
    """Contains information about traces in source code."""

    trace_index: int = Field()
    """The index position of this trace point in the trace stack."""
    path: Path = Field()
    """The source file of this trace. May not exist for compilation errors. May
    not be relative as it may be a system file."""
    name: str | None = Field(default=None)
    """The name of the symbol pointed to by the trace, if applicable."""
    line_idx: int = Field()
    """The location of the trace (0-based)."""
