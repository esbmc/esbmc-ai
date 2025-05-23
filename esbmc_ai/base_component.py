# Author: Yiannis Charalambous

"""Contains the base component ABC that is inherited by addons and system
components."""

import inspect
from abc import ABC
from typing import Any

import structlog

from esbmc_ai.base_config import BaseConfig
from esbmc_ai.config_field import ConfigField


class BaseComponent(ABC):
    """The base component class that is inherited by chat commands and verifiers
    and allows them to be loaded by the AddonLoader."""

    @classmethod
    def create(cls) -> "BaseComponent":
        """Factory method to instantiate a default version of this class."""
        # Check if __init__ takes only self (no required args)
        sig = inspect.signature(cls.__init__)
        params = list(sig.parameters.values())
        # params[0] is always 'self'
        if len(params) > 1 and any(p.default is p.empty for p in params[1:]):
            raise TypeError(
                f"{cls.__name__}.__init__ must take no arguments, override the "
                "create factory method to instantiate the object manually."
            )

        return cls()

    def __init__(self) -> None:
        super().__init__()

        self._config: BaseConfig
        self._name: str = self.__class__.__name__
        self._authors: str = ""
        self._logger: structlog.stdlib.BoundLogger = structlog.get_logger(
            f"{self._name}"
        )

    @property
    def logger(self) -> structlog.stdlib.BoundLogger:
        """Returns the logger of this class."""
        return self._logger

    @property
    def name(self) -> str:
        """Get the name of this component."""
        return self._name

    @property
    def authors(self) -> str:
        """Get the authors of this component."""
        return self._authors

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
