# Author: Yiannis Charalambous

"""This module holds the code for the base source code verifier."""

from dataclasses import dataclass
import re
from abc import ABC, abstractmethod
from typing import Any, Optional

from esbmc_ai.solution import SourceFile
from esbmc_ai.base_config import BaseConfig, ConfigField, default_scenario


class SourceCodeParseError(Exception):
    """Error that means that SolutionGenerator could not parse the source code
    to return the right format."""


class VerifierTimedOutException(Exception):
    """Error that means that ESBMC timed out and so the error could not be
    determined."""


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


class BaseSourceVerifier(ABC):
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

    def __init__(self, verifier_name: str) -> None:
        """Verifier name needs to be a valid TOML key."""
        super().__init__()
        pattern = re.compile(r"[a-zA-Z_]\w*")
        assert pattern.match(
            verifier_name
        ), f"Invalid toml-friendly verifier name: {verifier_name}"

        self.verifier_name: str = verifier_name
        self._config: BaseConfig

    @property
    def config(self) -> BaseConfig:
        return self._config

    @config.setter
    def config(self, value: BaseConfig) -> None:
        self._config: BaseConfig = value

    def get_config_fields(self) -> list[ConfigField]:
        """Called during initialization, this is meant to return all config
        fields that are going to be loaded from the config. The name that each
        field has will automatically be prefixed with {verifier name}."""
        return []

    def get_config_value(self, key: str) -> Any:
        """Loads a value from the config. If the value is defined in the namespace
        of the verifier name then that value will be returned.
        """
        return self._config.get_value(key)

    def verify_source(
        self,
        source_file: SourceFile,
        source_file_iteration: int = -1,
        **kwargs: Any,
    ) -> VerifierOutput:
        """Verifies source_file, the kwargs are optional arguments that are
        child dependent. For API purposes, the overriden method can provide the
        abilitiy to override values that would be loaded from the config by
        specifying them in the kwargs."""
        _ = source_file
        _ = source_file_iteration
        _ = kwargs
        raise NotImplementedError()

    def apply_formatting(self, verifier_output: str, format: str) -> str:
        """Applies a formatting style to the verifier output. This is used to
        change the output to a different form for when it is supplied to the
        LLM."""
        _ = verifier_output
        _ = format
        raise NotImplementedError()

    def get_error_line(self, verifier_output: str) -> Optional[int]:
        """Returns the line number of where the error as occurred."""
        _ = verifier_output
        raise NotImplementedError()

    def get_error_line_idx(self, verifier_output: str) -> Optional[int]:
        """Returns the line index of where the error as occurred."""
        _ = verifier_output
        raise NotImplementedError()

    def get_error_type(self, verifier_output: str) -> Optional[str]:
        """Returns a string of the type of error found by the verifier output."""
        _ = verifier_output
        raise NotImplementedError()

    def get_error_scenario(self, verifier_output: str) -> str:
        """Gets the scenario for fixing the error from verifier output"""
        _ = verifier_output
        return default_scenario
