# Author: Yiannis Charalambous

from abc import abstractmethod
from dataclasses import dataclass


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
