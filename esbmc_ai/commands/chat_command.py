# Author: Yiannis Charalambous

"""Contains things related to chat commands."""

from abc import ABC, abstractmethod
from typing import Any, Optional

from esbmc_ai.commands.command_result import CommandResult
from esbmc_ai.config_field import ConfigField
from esbmc_ai.base_config import BaseConfig


class ChatCommand(ABC):
    """Abstract Base Class for implementing chat commands."""

    def __init__(
        self,
        command_name: str = "",
        help_message: str = "",
        authors: str = "",
    ) -> None:
        super().__init__()
        self.command_name = command_name
        self.help_message = help_message
        self.authors = authors
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

    @abstractmethod
    def execute(self, **kwargs: Optional[Any]) -> Optional[CommandResult]:
        """The main entrypoint of the command. This is abstract and will need to
        be implemented."""
        raise NotImplementedError(f"Command {self.command_name} is not implemented.")
