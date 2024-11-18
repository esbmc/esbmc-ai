# Author: Yiannis Charalambous

"""This module holds the code for a dummy source code verifier."""

from typing import Any, Optional, override

from esbmc_ai.solution import SourceFile
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
    """The base class for creating a source verifier for ESBMC-AI. In order for
    this class to work with ESBMC-AI, the constructor must have default values
    to all arguments because it will be invoked without passing anything.

    Loading from the config will be permitted but it would be preferred if you
    use the base class method `get_config_value`. The fields of the config that
    are going to be loaded need to be declared and returned by the
    `get_config_fields` method. The config loader will automatically preppend
    the verifier_name declared to each key so that there are no clashes in the
    config. So the verifier "esbmc" will have for key "timeout" the following
    field in the config: "esbmc.timeout"."""

    def __init__(self) -> None:
        """Creates a new dummy verifier."""
        super().__init__(verifier_name="dummy_verifier")

    @override
    def get_config_fields(self) -> list[ConfigField]:
        return []

    @override
    def verify_source(
        self,
        source_file: SourceFile,
        source_file_iteration: int = -1,
        **kwargs: Any,
    ) -> DummyVerifierOutput:
        """Verifies source_file, the kwargs are optional arguments that are
        child dependent. For API purposes, the overriden method can provide the
        abilitiy to override values that would be loaded from the config by
        specifying them in the kwargs."""
        _ = source_file
        _ = source_file_iteration
        value = kwargs["value"] if "value" in kwargs else 0
        return DummyVerifierOutput(value, "")

    @override
    def apply_formatting(self, verifier_output: str, format: str) -> str:
        _ = format
        return verifier_output

    @override
    def get_error_line(self, verifier_output: str) -> Optional[int]:
        """1"""
        _ = verifier_output
        return 1

    @override
    def get_error_line_idx(self, verifier_output: str) -> Optional[int]:
        """0"""
        _ = verifier_output
        return 0

    @override
    def get_error_type(self, verifier_output: str) -> Optional[str]:
        """Returns empty string"""
        _ = verifier_output
        return ""
