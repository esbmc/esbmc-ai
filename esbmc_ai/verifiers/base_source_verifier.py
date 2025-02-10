# Author: Yiannis Charalambous

"""This module holds the code for the base source code verifier."""

import re
from typing import Any

from esbmc_ai.base_component import BaseComponent
from esbmc_ai.solution import Solution
from esbmc_ai.base_config import BaseConfig, default_scenario
from esbmc_ai.verifier_output import VerifierOutput
from esbmc_ai.program_trace import ProgramTrace


class SourceCodeParseError(Exception):
    """Error that means that SolutionGenerator could not parse the source code
    to return the right format."""


class VerifierTimedOutException(Exception):
    """Error that means that ESBMC timed out and so the error could not be
    determined."""


class BaseSourceVerifier(BaseComponent):
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

    def __init__(self, verifier_name: str, authors: str) -> None:
        """Verifier name needs to be a valid TOML key."""
        super().__init__(name=verifier_name, authors=authors)
        pattern = re.compile(r"[a-zA-Z_]\w*")
        assert pattern.match(
            verifier_name
        ), f"Invalid toml-friendly verifier name: {verifier_name}"

        self._config: BaseConfig

    @property
    def verifier_name(self) -> str:
        """Alias for name"""
        return self.name

    def verify_source(
        self,
        solution: Solution,
        **kwargs: Any,
    ) -> VerifierOutput:
        """Verifies source_file, the kwargs are optional arguments that are
        implementation dependent."""
        _ = solution
        _ = kwargs
        raise NotImplementedError()

    def apply_formatting(self, verifier_output: str, format: str) -> str:
        """Applies a formatting style to the verifier output. This is used to
        change the output to a different form for when it is supplied to the
        LLM."""
        _ = verifier_output
        _ = format
        raise NotImplementedError()

    def get_error_line(self, verifier_output: str) -> int:
        """Returns the line number of where the error as occurred."""
        _ = verifier_output
        raise NotImplementedError()

    def get_error_line_idx(self, verifier_output: str) -> int:
        """Returns the line index of where the error as occurred."""
        _ = verifier_output
        raise NotImplementedError()

    def get_error_type(self, verifier_output: str) -> str:
        """Returns a string of the type of error found by the verifier output."""
        _ = verifier_output
        raise NotImplementedError()

    def get_error_scenario(self, verifier_output: str) -> str:
        """Gets the scenario for fixing the error from verifier output"""
        _ = verifier_output
        return default_scenario

    def get_trace(self, verifier_output: str) -> list[ProgramTrace]:
        """Returns the trace given a counterexample."""
        _ = verifier_output
        raise NotImplementedError()
