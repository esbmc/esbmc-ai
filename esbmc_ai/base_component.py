# Author: Yiannis Charalambous

"""Contains the base component ABC that is inherited by addons and system
components."""

import inspect
from abc import ABC
import os
from pathlib import Path
import re

from typing import Any, cast, override
from pydantic import FilePath
from pydantic.fields import FieldInfo
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)
from pydantic_settings.sources import InitSettingsSource
import structlog
import tomllib

from esbmc_ai.config import Config


class DictConfigSettingsSource(PydanticBaseSettingsSource):
    """Custom settings source that loads from a pre-loaded dictionary."""

    def __init__(
        self, settings_cls: type[BaseSettings], config_dict: dict[str, Any]
    ) -> None:
        super().__init__(settings_cls)
        self.config_dict = config_dict

    @override
    def get_field_value(
        self, field: FieldInfo, field_name: str
    ) -> tuple[Any, str, bool]:
        """Get field value from the config dictionary."""
        _ = field
        if field_name in self.config_dict:
            return self.config_dict[field_name], field_name, False
        return None, field_name, False

    def __call__(self) -> dict[str, Any]:
        """Return the config dictionary."""
        return self.config_dict


class BaseComponentConfig(BaseSettings):
    """Pydantic BaseSettings preconfigured to be able to load config values.

    Component configs are loaded from the TOML file under the 'addons.<component_name>'
    section by ComponentManager.

    The component name is passed via _component_name kwarg to __init__ and is
    extracted in settings_customise_sources to determine the TOML table header.
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

    def __init__(self, **values: Any) -> None:
        """Used to provide static analyzers type annotations so that we don't get
        errors in ComponentManager."""
        super().__init__(**values)

    @override
    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type["BaseSettings"],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        # Get config file path from global Config
        # Note: .env is already loaded by the global Config before component
        # configs are loaded
        config_file_path: FilePath | None = Config().config_file

        sources: list[PydanticBaseSettingsSource] = [
            init_settings,
            env_settings,
            dotenv_settings,
        ]

        # Add TOML config source if config file is specified
        if config_file_path:
            config_file: Path = Path(config_file_path).expanduser()
            if config_file.exists():
                # Cast to InitSettingsSource to access init_kwargs
                init_source: InitSettingsSource = cast(
                    InitSettingsSource, init_settings
                )

                # Extract component name and builtin flag from init_settings if
                # provided
                component_name: str = cast(
                    str, init_source.init_kwargs.get("_component_name")
                )
                builtin: bool = cast(bool, init_source.init_kwargs.get("_builtin"))

                # If a component name is actually given, then the config will be
                # loaded from the file. If none, then nothjing is loaded from the
                # config file, instead the other sources are used only.
                if component_name:
                    # Load TOML file and extract addons.<component_name> section
                    with open(config_file, "rb") as f:
                        config_data: dict = tomllib.load(f)

                    # Get the component-specific config from either <component_name>
                    # or addons.<component_name>
                    component_config: dict = config_data
                    if builtin:
                        component_config = config_data.get(component_name, {})
                    else:
                        component_config = config_data.get("addons", {}).get(
                            component_name, {}
                        )

                    # Add custom dict source with component config
                    if component_config:
                        sources.append(
                            DictConfigSettingsSource(settings_cls, component_config)
                        )

        # Priority order: init > env > dotenv > TOML > file_secret
        sources.append(file_secret_settings)
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
        sig: inspect.Signature = inspect.signature(cls.__init__)
        params: list[inspect.Parameter] = list(sig.parameters.values())
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
