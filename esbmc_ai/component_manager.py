# Author: Yiannis Charalambous

"""Module contains class for keeping track and managing built-in base
components."""

from types import MappingProxyType
from typing import cast

import structlog

from esbmc_ai.base_component import BaseComponent, BaseComponentConfig
from esbmc_ai.chat_command import ChatCommand
from esbmc_ai.singleton import SingletonMeta
from esbmc_ai.verifiers.base_source_verifier import BaseSourceVerifier
from esbmc_ai.log_utils import LogCategories


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

        # Internal storage
        self._builtin_commands: dict[str, ChatCommand] = {}
        self._addon_commands: dict[str, ChatCommand] = {}
        self._builtin_verifiers: dict[str, BaseSourceVerifier] = {}
        self._addon_verifiers: dict[str, BaseSourceVerifier] = {}
        self._verifier: BaseSourceVerifier | None = None

        # Cached combined dictionaries for efficiency
        self._all_commands_cache: dict[str, ChatCommand] | None = None
        self._all_verifiers_cache: dict[str, BaseSourceVerifier] | None = None
        self._all_components_cache: dict[str, BaseComponent] | None = None
        self._builtin_components_cache: dict[str, BaseComponent] | None = None
        self._addon_components_cache: dict[str, BaseComponent] | None = None

    def _invalidate_caches(self) -> None:
        """Invalidate all cached combined dictionaries."""
        self._all_commands_cache = None
        self._all_verifiers_cache = None
        self._all_components_cache = None
        self._builtin_components_cache = None
        self._addon_components_cache = None

    # ====================
    # Commands API
    # ====================

    @property
    def builtin_commands(self) -> MappingProxyType[str, ChatCommand]:
        """Returns a read-only view of all builtin commands."""
        return MappingProxyType(self._builtin_commands)

    @property
    def addon_commands(self) -> MappingProxyType[str, ChatCommand]:
        """Returns a read-only view of all addon commands."""
        return MappingProxyType(self._addon_commands)

    @property
    def commands(self) -> MappingProxyType[str, ChatCommand]:
        """Returns a read-only view of all commands (builtin + addon)."""
        if self._all_commands_cache is None:
            self._all_commands_cache = self._builtin_commands | self._addon_commands
        return MappingProxyType(self._all_commands_cache)

    @property
    def command_names(self) -> list[str]:
        """Returns a list of all command names."""
        return list(self.commands.keys())

    def add_command(self, command: ChatCommand, builtin: bool = False) -> None:
        """Add a command to the manager."""
        if builtin:
            self._builtin_commands[command.name] = command
        else:
            self._addon_commands[command.name] = command
        self._invalidate_caches()

    def remove_command(self, name: str) -> bool:
        """Remove a command by name. Returns True if removed, False if not found."""
        removed = False
        if name in self._builtin_commands:
            del self._builtin_commands[name]
            removed = True
        if name in self._addon_commands:
            del self._addon_commands[name]
            removed = True
        if removed:
            self._invalidate_caches()
        return removed

    def get_command(self, name: str) -> ChatCommand | None:
        """Get a command by name."""
        return self.commands.get(name)

    def set_builtin_commands(self, builtin_commands: list[ChatCommand]) -> None:
        """Sets the builtin commands, replacing any existing builtin commands."""
        self._builtin_commands = {cmd.command_name: cmd for cmd in builtin_commands}
        self._invalidate_caches()

    # ====================
    # Verifiers API
    # ====================

    @property
    def builtin_verifiers(self) -> MappingProxyType[str, BaseSourceVerifier]:
        """Returns a read-only view of all builtin verifiers."""
        return MappingProxyType(self._builtin_verifiers)

    @property
    def addon_verifiers(self) -> MappingProxyType[str, BaseSourceVerifier]:
        """Returns a read-only view of all addon verifiers."""
        return MappingProxyType(self._addon_verifiers)

    @property
    def verifiers(self) -> MappingProxyType[str, BaseSourceVerifier]:
        """Returns a read-only view of all verifiers (builtin + addon)."""
        if self._all_verifiers_cache is None:
            self._all_verifiers_cache = self._builtin_verifiers | self._addon_verifiers
        return MappingProxyType(self._all_verifiers_cache)

    @property
    def verifier(self) -> BaseSourceVerifier:
        """Returns the currently selected verifier."""
        assert self._verifier, "Verifier is not set..."
        return self._verifier

    @verifier.setter
    def verifier(self, value: BaseSourceVerifier) -> None:
        assert value.name in self.verifiers, f"Unregistered verifier set: {value.name}"
        self._verifier = value

    def add_verifier(self, verifier: BaseSourceVerifier, builtin: bool = True) -> None:
        """Adds a verifier."""
        from esbmc_ai.config import Config

        if builtin:
            self._builtin_verifiers[verifier.name] = verifier
        else:
            self._addon_verifiers[verifier.name] = verifier
        verifier.global_config = Config()
        self._invalidate_caches()

    def remove_verifier(self, name: str) -> bool:
        """Remove a verifier by name. Returns True if removed, False if not found."""
        removed = False
        if name in self._builtin_verifiers:
            del self._builtin_verifiers[name]
            removed = True
        if name in self._addon_verifiers:
            del self._addon_verifiers[name]
            removed = True
        if removed:
            self._invalidate_caches()
        return removed

    def set_verifier_by_name(self, value: str) -> None:
        """Set the active verifier by name."""
        self.verifier = self.verifiers[value]
        self._logger.info(f"Main Verifier: {value}")

    def get_verifier(self, value: str) -> BaseSourceVerifier | None:
        """Get a verifier by name."""
        return self.verifiers.get(value)

    # ====================
    # Components API
    # ====================

    @property
    def builtin_components(self) -> MappingProxyType[str, BaseComponent]:
        """Returns a read-only view of all builtin components (commands + verifiers)."""
        if self._builtin_components_cache is None:
            self._builtin_components_cache = cast(
                dict[str, BaseComponent], self._builtin_commands
            ) | cast(dict[str, BaseComponent], self._builtin_verifiers)
        return MappingProxyType(self._builtin_components_cache)

    @property
    def addon_components(self) -> MappingProxyType[str, BaseComponent]:
        """Returns a read-only view of all addon components (commands + verifiers)."""
        if self._addon_components_cache is None:
            self._addon_components_cache = cast(
                dict[str, BaseComponent], self._addon_commands
            ) | cast(dict[str, BaseComponent], self._addon_verifiers)

        assert self._addon_components_cache is not None
        return MappingProxyType(self._addon_components_cache)

    @property
    def components(self) -> MappingProxyType[str, BaseComponent]:
        """Returns a read-only view of all components (builtin + addon commands + verifiers)."""
        if self._all_components_cache is None:
            self._all_components_cache = (
                cast(dict[str, BaseComponent], self._builtin_commands)
                | cast(dict[str, BaseComponent], self._addon_commands)
                | cast(dict[str, BaseComponent], self._builtin_verifiers)
                | cast(dict[str, BaseComponent], self._addon_verifiers)
            )
        return MappingProxyType(self._all_components_cache)

    def get_component(self, name: str) -> BaseComponent | None:
        """Get a component by name (command or verifier)."""
        return self.components.get(name)

    def load_component_config(self, component: BaseComponent, builtin: bool) -> None:
        """Load component-specific configuration.

        Component configs are loaded automatically via BaseComponentConfig.settings_customise_sources(),
        which loads from TOML, env vars, and .env files.
        """
        try:
            # Check if component has a config instance set
            if component.config is None:
                raise NotImplementedError()

            # Get the config class from the existing instance
            config_class: type[BaseComponentConfig] = type(component.config)

            # Instantiate the config - settings_customise_sources will handle
            # actual loading. Pass component_name via _component_name parameter
            # and builtin via _builtin so BaseComponentConfig can use it for
            # TOML table header. These are not defined fields but captured via
            # extra="ignore" and used in settings_customise_sources.
            loaded_config = config_class(  # type: ignore[call-arg]
                _component_name=component.name, _builtin=builtin
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
