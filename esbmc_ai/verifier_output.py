# Author: Yiannis Charalambous

from abc import abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

from esbmc_ai.program_trace import ProgramTrace

if TYPE_CHECKING:
    from esbmc_ai.solution import Solution


@dataclass
class VerifierOutput:
    """Class that represents the verifier output."""

    return_code: int
    """The return code of the verifier."""
    output: str
    """The output of the verifier."""

    @abstractmethod
    def successful(self) -> bool:
        """If the verification was successful."""
        raise NotImplementedError()

    def get_error_line(self) -> int:
        """Returns the line number of where the error as occurred."""
        raise NotImplementedError()

    def get_error_line_idx(self) -> int:
        """Returns the line index of where the error as occurred."""
        raise NotImplementedError()

    def get_error_type(self) -> str:
        """Returns a string of the type of error found by the verifier output."""
        raise NotImplementedError()

    def get_stack_trace(self) -> str:
        """Gets the stack trace that points to the error."""
        raise NotImplementedError()

    def get_trace(
        self,
        solution: "Solution",
        include_libs=False,
        add_missing_source=False,
    ) -> list[ProgramTrace]:
        """Returns a more detailed trace. Each line that causes the error is
        returned. Given a counterexample."""
        _ = solution
        _ = include_libs
        _ = add_missing_source
        raise NotImplementedError()
