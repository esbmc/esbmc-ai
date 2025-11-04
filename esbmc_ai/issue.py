# Author: Yiannis Charalambous


from typing import Literal, override
from pathlib import Path

from langchain_core.load.serializable import Serializable
from pydantic import Field

from esbmc_ai.program_trace import ProgramTrace


class Issue(Serializable):
    """Generic issue/error representation.

    Uses stack_trace as the single source of truth for location information.
    All issues must have at least one trace point describing the error location.
    Simple errors have a single trace point, while complex errors have multiple
    trace points.
    """

    error_type: str = Field(description="Category/type of error.")
    """Category/type of error."""
    message: str = Field(description="Error description.")
    """Error description."""
    stack_trace: list[ProgramTrace] = Field(
        min_length=1,
        description="Stack trace as structured data. At least one trace point required.",
    )
    """Stack trace as structured data. At least one trace point required."""
    severity: Literal["error", "warning", "info"] = Field(
        default="error", description="Severity level."
    )
    """Severity level."""

    @classmethod
    @override
    def is_lc_serializable(cls) -> bool:
        """Enable langchain serialization."""
        return True

    # Convenience properties
    # Note: All properties derive from the last trace point (stack_trace[-1]) as this
    # represents the point of failure in the stack trace. Earlier trace points show
    # the call chain leading to the error.

    @property
    def severity_level(self) -> int:
        """Returns the severity as an int."""
        match self.severity:
            case "info":
                return 0
            case "warning":
                return 1
            case "error":
                return 2

    @property
    def file_path(self) -> Path:
        """Path to file with issue (derived from last trace point)."""
        return self.stack_trace[-1].path

    @property
    def line_index(self) -> int:
        """Line index where the error occurred (derived from last trace point, 0-based)"""
        return self.stack_trace[-1].line_idx

    @property
    def line_number(self) -> int:
        """Line number where error occurred (derived from last trace point, 1-based)."""
        return self.stack_trace[-1].line_idx + 1

    @property
    def function_name(self) -> str | None:
        """Function name where error occurred (derived from last trace point)."""
        return self.stack_trace[-1].name


class VerifierIssue(Issue):
    """Verifier-specific issue with additional verification data.

    This class extends Issue to support verifiers like ESBMC that can provide
    counterexamples in addition to stack traces:

    - stack_trace: Traditional function call stack showing the path to the error
    - counterexample: Program state trace showing variable values and execution
      states that lead to the bug. This is specific to model checkers and formal
      verification tools like ESBMC.

    Note: Not all verifiers support counterexamples (e.g., pytest only provides
    stack traces). Use this class only when counterexample data is available.
    """

    counterexample: list[ProgramTrace] = Field(
        description="Counterexample demonstrating bug."
    )
    """Counterexample demonstrating bug."""
