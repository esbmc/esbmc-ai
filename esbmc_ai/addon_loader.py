# Author: Yiannis Charalambous

"""This module contains code regarding configuring and loading addon modules."""

import traceback
import sys
import importlib
import structlog

from esbmc_ai.base_component import BaseComponent
from esbmc_ai.chat_command import ChatCommand
from esbmc_ai.verifiers.base_source_verifier import BaseSourceVerifier
from esbmc_ai.config import Config
from esbmc_ai.singleton import SingletonMeta


class AddonLoader(metaclass=SingletonMeta):
    """The addon loader manages loading addon modules and initializing them."""

    addon_prefix: str = "addons"

    def __init__(self, config: Config | None = None) -> None:
        self._logger: structlog.stdlib.BoundLogger = structlog.get_logger(
            self.__class__.__name__
        )
        self._logger.debug("Loading Addons...")

        assert config
        self._config: Config = config

        # Keeps track of the addons that have been loaded.
        self._loaded_addons: dict[str, BaseComponent] = {}

        # Dev mode: Ensure the current directory is in sys.path in order for
        # relative addon modules to be imported (used for dev purposes).
        if self._config.dev_mode and "" not in sys.path:
            sys.path.insert(0, "")

        # Load the config fields.
        if self._config.addon_modules:
            print("Loading Addons:")

        for m in self._config.addon_modules:
            addons: list[BaseComponent] = self.load_addons_module(m)
            for addon in addons:
                print(f"\t* {addon.name} by {addon.authors}")

    @property
    def chat_command_addons(self) -> dict[str, ChatCommand]:
        """Returns all the addon chat commands."""
        return {
            addon_name: addon
            for addon_name, addon in self.loaded_addons.items()
            if isinstance(addon, ChatCommand)
        }

    @property
    def chat_command_addon_names(self) -> list[str]:
        """Returns all the addon chat command names."""
        return list(
            addon.name
            for addon in self.loaded_addons.values()
            if isinstance(addon, ChatCommand)
        )

    @property
    def verifier_addons(self) -> dict[str, BaseSourceVerifier]:
        """Returns all the addon verifiers."""
        return {
            addon_name: addon
            for addon_name, addon in self.loaded_addons.items()
            if isinstance(addon, BaseSourceVerifier)
        }

    @property
    def verifier_addon_names(self) -> list[str]:
        """Returns all the addon verifier names."""
        return list(
            addon.name
            for addon in self.loaded_addons
            if isinstance(addon, BaseSourceVerifier)
        )

    @property
    def loaded_addons(self) -> dict[str, BaseComponent]:
        return self._loaded_addons

    def get_addon_by_name(self, name: str) -> BaseComponent | None:
        """Returns an addon by the addon name defined in __init__."""
        for addon in self.loaded_addons.values():
            if addon.name == name:
                return addon
        return None

    def load_addons_module(self, module_name: str) -> list[BaseComponent]:
        """Loads an addon, needs to expose a BaseComponent.

        Will import addon modules that exist and iterate through the exposed
        attributes, will then get all available exposed classes and store them."""

        result: list = []
        try:
            m = importlib.import_module(module_name)
            for exposed_class_name in getattr(m, "__all__"):
                # Get the class from the __all__
                exposed_class = getattr(m, exposed_class_name)
                # Check if valid addon type and import
                if issubclass(exposed_class, BaseComponent):
                    addon: BaseComponent = self.init_base_component(exposed_class)
                    self._loaded_addons[addon.name] = addon
                    result.append(addon)

        except ModuleNotFoundError as e:
            self._logger.error("error while loading module: traceback:")
            traceback.print_tb(e.__traceback__)
            self._logger.error(f"could not import module: {module_name}: {e}")
            sys.exit(1)
        except AttributeError as e:
            self._logger.error(f"module {module_name} is invalid: {e}")
            sys.exit(1)
        return result

    def init_base_component(self, t: type[BaseComponent]) -> BaseComponent:
        # Initialize class.
        addon: BaseComponent = t.create()
        self._logger.debug(f"Loading addon: {addon.__class__.__name__}")

        # Register config with modules
        addon.global_config = self._config

        # Load component-specific configuration using ComponentManager
        from esbmc_ai.component_manager import ComponentManager

        ComponentManager().load_component_config(addon, builtin=False)

        return addon
