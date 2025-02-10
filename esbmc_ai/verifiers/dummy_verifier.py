# Author: Yiannis Charalambous

"""This module holds the code for a dummy source code verifier."""

from typing import Any, Optional, override

from esbmc_ai.solution import Solution
from esbmc_ai.config import ConfigField
from esbmc_ai.verifiers.base_source_verifier import BaseSourceVerifier, VerifierOutput


class DummyVerifierOutput(VerifierOutput):
    """Class that represents the dummy verifier output. The output is going to
    be blank, and the return code can be set to whatever value. If it is 0, it
    will be successful."""

    return_code: int
    """The return code of the verifier."""
    output: str
    """The output of the verifier."""

    @override
    def successful(self) -> bool:
        return self.return_code == 0


class DummyVerifier(BaseSourceVerifier):
    """Dummy verifier with pre-configured responses. Used for testing."""

    def __init__(
        self, responses: Optional[list[str]] = None, load_config: bool = False
    ) -> None:
        """Creates a new dummy verifier."""
        super().__init__(verifier_name="dummy_verifier", authors="")
        self._responses: Optional[list[str]] = responses
        self._current_response: int = 0
        self._load_config = load_config

    @property
    def responses(self) -> list[str]:
        """The list of responses to give for each call to verify_source."""
        if self._load_config:
            return (
                self._responses
                if self._responses
                else self.get_config_value("responses")
            )
        else:
            return self._responses if self._responses else []

    @responses.setter
    def responses(self, value: Optional[list[str]]) -> None:
        self._responses = value

    def set_response_counter(self, value: Optional[int] = None) -> None:
        """Sets the index of the response to use."""
        self._current_response = value if value else 0
        assert 0 <= self._current_response < len(self.responses), (
            "Responses index set out of range: 0 <= "
            f"{self._current_response} < {len(self.responses)}"
        )

    @override
    def get_config_fields(self) -> list[ConfigField]:
        return [
            ConfigField(
                name="responses",
                default_value=[],
                error_message="Invalid, needs to be an array of strings.",
                validate=lambda v: isinstance(v, str),
            )
        ]

    @override
    def verify_source(
        self,
        solution: Solution,
        **kwargs: Any,
    ) -> DummyVerifierOutput:
        """Verifies source_file, the kwargs are optional arguments that are
        child dependent. For API purposes, the overriden method can provide the
        abilitiy to override values that would be loaded from the config by
        specifying them in the kwargs."""
        value = kwargs["value"] if "value" in kwargs else 0
        _ = solution
        return DummyVerifierOutput(value, self.responses[self._current_response])

    @override
    def apply_formatting(self, verifier_output: str, format: str) -> str:
        _ = format
        return verifier_output

    @override
    def get_error_line(self, verifier_output: str) -> int:
        """1"""
        _ = verifier_output
        return 1

    @override
    def get_error_line_idx(self, verifier_output: str) -> int:
        """0"""
        _ = verifier_output
        return 0

    @override
    def get_error_type(self, verifier_output: str) -> str:
        """Returns empty string"""
        _ = verifier_output
        return ""
