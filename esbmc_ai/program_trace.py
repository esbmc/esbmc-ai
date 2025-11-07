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


class CounterexampleProgramTrace(ProgramTrace):
    """Program trace with assignment information from counterexample states.

    This class extends ProgramTrace to capture the variable assignments that
    led to a verification failure. Used by verifiers like ESBMC that provide
    counterexample traces showing the state of variables at each step.
    """

    assignment: str | None = Field(default=None)
    """The assignment statement(s) for this trace state. Contains the variable
    assignments from the counterexample, e.g., 'dist = { 0, 0, 0, 0, 0 }' or
    'dist[0] = 2147483647 (01111111 11111111 11111111 11111111)'. May be None
    if the state has no assignment information."""
