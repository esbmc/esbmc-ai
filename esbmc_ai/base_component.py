# Author: Yiannis Charalambous

"""Contains the base component ABC that is inherited by addons and system
components."""

from abc import ABC
from typing import Any

from esbmc_ai.base_config import BaseConfig
from esbmc_ai.config_field import ConfigField


class BaseComponent(ABC):
    """The base component class that is inherited by chat commands and verifiers
    and allows them to be loaded by the AddonLoader."""

    def __init__(self, name: str, authors: str) -> None:
        super().__init__()

        self._config: BaseConfig
        self.name: str = name
        self.authors: str = authors

    @property
    def config(self) -> BaseConfig:
        """Gets the config for this chat command."""
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
