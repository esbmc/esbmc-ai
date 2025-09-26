# Author: Yiannis Charalambous

"""Module contains class for keeping track and managing built-in base
components."""


import structlog

from esbmc_ai.chat_command import ChatCommand
from esbmc_ai.singleton import SingletonMeta
from esbmc_ai.verifiers.base_source_verifier import BaseSourceVerifier
from esbmc_ai.log_utils import LogCategories
from esbmc_ai.base_component import BaseComponent, BaseComponentConfig

from pydantic_settings import PydanticBaseSettingsSource
from pydantic_settings import CliApp


class ComponentManager(metaclass=SingletonMeta):
    """Class for keeping track of and initializing local components.

    Local components are classes derived from BaseComponent that use base
    component features (maybe for readability). Built-in commands, built-in
    verifiers for example.

    Manages all the verifiers that are used. Can get the appropriate one based
    on the config."""

    def __init__(self) -> None:
        self._logger: structlog.stdlib.BoundLogger = structlog.get_logger(
            self.__class__.__name__
        ).bind(category=LogCategories.SYSTEM)
        self.verifiers: dict[str, BaseSourceVerifier] = {}
        self._verifier: BaseSourceVerifier | None = None

        self._builtin_commands: dict[str, ChatCommand] = {}
        self._addon_commands: dict[str, ChatCommand] = {}

        # Store settings sources for component configuration loading
        self._settings_sources: list[PydanticBaseSettingsSource] | None = None

    @property
    def verfifier(self) -> BaseSourceVerifier:
        """Returns the verifier that is selected."""
        assert self._verifier, "Verifier is not set..."
        return self._verifier

    @verfifier.setter
    def verifier(self, value: BaseSourceVerifier) -> None:
        assert (
            value not in self.verifiers
        ), f"Unregistered verifier set: {value.verifier_name}"
        self._verifier = value

    def add_verifier(self, verifier: BaseSourceVerifier) -> None:
        """Adds a verifier."""
        from esbmc_ai.config import Config

        self.verifiers[verifier.name] = verifier
        verifier.global_config = Config()

    def set_verifier_by_name(self, value: str) -> None:
        self.verifier = self.verifiers[value]
        self._logger.info(f"Main Verifier: {value}")

    def get_verifier(self, value: str) -> BaseSourceVerifier | None:
        return self.verifiers.get(value)

    @property
    def commands(self) -> dict[str, ChatCommand]:
        """Returns all commands."""
        return self._builtin_commands | self._addon_commands

    @property
    def command_names(self) -> list[str]:
        """Returns a list of built-in commands. This is a reference to the
        internal list."""
        return list(self.commands.keys())

    @property
    def builtin_commands(self) -> dict[str, ChatCommand]:
        return self._builtin_commands

    @property
    def addon_commands(self) -> dict[str, ChatCommand]:
        return self._addon_commands

    def add_command(self, command: ChatCommand, builtin: bool = False) -> None:
        if builtin:
            self._builtin_commands[command.name] = command
        else:
            self._addon_commands[command.name] = command

    def set_builtin_commands(self, builtin_commands: list[ChatCommand]) -> None:
        """Sets the builtin commands."""
        self._builtin_commands = {cmd.command_name: cmd for cmd in builtin_commands}

    def set_settings_sources(
        self, settings_sources: list[PydanticBaseSettingsSource]
    ) -> None:
        """Set the settings sources for component configuration loading."""
        self._settings_sources = settings_sources

    def load_component_config(self, component: BaseComponent) -> None:
        """Load component-specific configuration using the same settings sources as main config."""
        if self._settings_sources is None:
            self._logger.warn(
                f"Settings sources not set, skipping config load for {component.name}"
            )
            return

        try:
            # Check if component has a config instance set
            if component.config is None:
                self._logger.debug(f"Component {component.name} has no custom config")
                return

            # Get the config class from the existing instance
            config_class = type(component.config)

            # Create configuration instance using the global settings sources hierarchy
            loaded_config = CliApp.run(
                config_class, settings_sources=self._settings_sources
            )

            # Replace the component's config with the loaded one
            component.config = loaded_config
            self._logger.debug(f"Loaded component config for {component.name}")

        except NotImplementedError:
            self._logger.debug(f"No config for component: {component.name}")

        except Exception as e:
            self._logger.error(
                f"Failed to load config for component {component.name}: {e}"
            )
