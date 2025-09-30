# Author: Yiannis Charalambous

"""Contains the base component ABC that is inherited by addons and system
components."""

import inspect
from abc import ABC
import os
from pathlib import Path
import re

from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    TomlConfigSettingsSource,
)
import structlog

from esbmc_ai.config import Config


class BaseComponentConfig(BaseSettings):
    """Pydantic BaseSettings preconfigured to be able to load config values.

    Component configs are loaded from the TOML file under the 'addons.<component_name>'
    section by ComponentManager.
    """

    # Used to allow loading from cli and env.
    model_config = SettingsConfigDict(
        env_prefix="ESBMCAI_",
        env_file=".env",
        env_file_encoding="utf-8",
        # Do not parse CLI args in component configs - only the main Config should
        cli_parse_args=False,
        # Ignore extra fields from .env file that don't match the component schema
        extra="ignore",
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type["BaseSettings"],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        # Manually load .env file to get ESBMCAI_CONFIG_FILE before creating sources
        from dotenv import load_dotenv
        load_dotenv(".env", override=False)

        # Get config file path from environment variable
        config_file_path = os.getenv("ESBMCAI_CONFIG_FILE")

        sources = [init_settings]

        # Add TOML config source if config file is specified
        # Component configs will get their specific section via init_settings
        if config_file_path:
            config_file = Path(config_file_path).expanduser()
            if config_file.exists():
                sources.append(TomlConfigSettingsSource(settings_cls, config_file))

        # Priority order: init > TOML > env > dotenv > file_secret
        sources.extend([env_settings, dotenv_settings, file_secret_settings])
        return tuple(sources)


class BaseComponent(ABC):
    """The base component class that is inherited by chat commands and verifiers
    and allows them to be loaded by the AddonLoader.

    The model is mapped to the config via the prefix of the name it has. So if
    the name of a BaseComponent is "MyComponent" and we have a Field "my_field"
    then the value from config loaded will be "addons.MyComponent.my_field".
    """

    @classmethod
    def create(cls) -> "BaseComponent":
        """Factory method to instantiate a default version of this class. Used
        by AddonLoader."""
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

        self._global_config: Config
        self._name: str = self.__class__.__name__

        pattern = re.compile(r"[a-zA-Z_]\w*")
        assert pattern.match(
            self._name
        ), f"Invalid toml-friendly verifier name: {self._name}"

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
    def global_config(self) -> Config:
        """Gets the config for this chat command."""
        return self._global_config

    @global_config.setter
    def global_config(self, value: Config) -> None:
        self._global_config = value

    @property
    def config(self) -> BaseComponentConfig:
        """Gets the component-specific configuration.

        This property provides access to the component's configuration.
        The configuration must be set by the ComponentManager before accessing.

        Returns:
            The component's configuration instance.

        Raises:
            RuntimeError: If configuration has not been set.
        """
        raise NotImplementedError(f"Configuration not set for component {self.name}")

    @config.setter
    def config(self, value: BaseComponentConfig) -> None:
        """Sets the component-specific configuration.

        Args:
            value: The configuration instance for this component.
        """
        _ = value
        raise NotImplementedError(f"Configuration not set for component {self.name}")
