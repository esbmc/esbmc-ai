# Author: Yiannis Charalambous

from dataclasses import dataclass
from typing import Literal


@dataclass
class ProgramTrace:
    """Contains information about traces in source code."""

    trace_type: Literal["function", "statement", "file"]
    """The scope of this trace."""
    file_name: str
    """The filename of this trace. The SourceFile can then be extracted from the
    solution."""
    name: str
    """The name of the symbol, if applicable."""
    line_idx: int
    """The location of the trace."""
