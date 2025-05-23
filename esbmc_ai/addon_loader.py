# Author: Yiannis Charalambous

"""This module contains code regarding configuring and loading addon modules."""

import inspect
from typing import Any
import traceback
import sys
import importlib
from importlib.util import find_spec
from importlib.machinery import ModuleSpec
import structlog
from typing_extensions import Optional

from esbmc_ai.base_component import BaseComponent
from esbmc_ai.chat_command import ChatCommand
from esbmc_ai.verifiers.base_source_verifier import BaseSourceVerifier
from esbmc_ai.config_field import ConfigField
from esbmc_ai.config import Config
from esbmc_ai.singleton import SingletonMeta


class AddonLoader(metaclass=SingletonMeta):
    """The addon loader manages loading addon modules. This includes:
    * Managing the config fields of the addons.
    * Dynamically loading the fields when the addons request them.

    When an addon requests a config value from an addon that is not loaded, that
    addon's config fields get loaded. This means that addons will have dependency
    management (as long as there's no loops).
    """

    addon_prefix: str = "addons"

    def __init__(self, config: Config | None = None) -> None:
        self._logger: structlog.stdlib.BoundLogger = structlog.get_logger(
            self.__class__.__name__
        )
        self._logger.debug("Loading Addons...")

        assert config
        self._config: Config = config
        self._config.on_load_value.append(self._on_get_config_value)

        # Keeps track of the addons that have been loaded.
        self._loaded_addons: dict[str, BaseComponent] = {}
        # Keeps track of the addons that had their config fields initialized.
        self._initialized_addons: set[BaseComponent] = set()

        # Dev mode: Ensure the current directory is in sys.path in order for
        # relative addon modules to be imported (used for dev purposes).
        if self._config.get_value("dev_mode") and "" not in sys.path:
            sys.path.insert(0, "")

        # Register field with Config to know which modules to load.
        config.add_config_field(
            ConfigField(
                name="addon_modules",
                default_value=[],
                validate=self._validate_addon_modules,
                error_message="couldn't find module: must be a list of Python modules to load",
                help_message="The addon modules to load during startup. Additional "
                "modules may be loaded by the specified modules as dependencies.",
            ),
        )

        # Load the config fields.
        if self._config.get_value("addon_modules"):
            print("Loading Addons:")
        for m in self._config.get_value("addon_modules"):
            addons: list[BaseComponent] = self.load_addons(m)
            for addon in addons:
                print(f"\t* {addon.name} by {addon.authors}")

        # Init the verifier.name field for the main config. The reason this is
        # not part of the main config is that verifiers are treated as addons,
        # even internally.
        self._config.add_config_field(
            ConfigField(
                name="verifier.name",
                default_value="esbmc",
                validate=lambda v: isinstance(v, str)
                and v in self.verifier_addon_names + ["esbmc"],
                error_message="Invalid verifier name specified.",
                help_message="The verifier to use. Default is ESBMC.",
            )
        )

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

    @staticmethod
    def _validate_addon_modules(mods: str) -> bool:
        """Validates that a module exists."""
        for m in mods:
            if not isinstance(m, str):
                return False
            spec: Optional[ModuleSpec] = find_spec(m)
            if spec is None:
                return False
        return True

    def _on_get_config_value(self, name: str) -> None:
        """Checks if an addon's values were loaded prior to it requesting an
        a value. If they weren't load them. This allows for addon ConfigFields
        to be loaded dynamically.

        Will only check for ConfigFields that have a name that is prefixed with
        "addon."."""
        # Check if it references an addon and is not loaded.
        split_key: list[str] = name.split(".")
        if split_key[0] == AddonLoader.addon_prefix and len(split_key) > 1:
            # Check if the addon is valid.
            addon: BaseComponent | None = self.get_addon_by_name(split_key[1])
            if addon in self._initialized_addons:
                return
            elif addon:
                self._load_addon_config(addon)
                self._initialized_addons.add(addon)
            else:
                raise KeyError(f"AddonLoader: failed to load config of addon {name}")

    def get_addon_by_name(self, name: str) -> BaseComponent | None:
        """Returns an addon by the addon name defined in __init__."""
        for addon in self.loaded_addons.values():
            if addon.name == name:
                return addon
        return None

    def _get_addon_resolved_fields(self, addon: BaseComponent) -> list[ConfigField]:
        """Returns the addons's config fields. After resolving each field to
        their namespace using the name of the component."""
        # If an addon prefix is defined, then add a .
        addons_prefix: str = (
            AddonLoader.addon_prefix + "." if AddonLoader.addon_prefix else ""
        )

        fields_resolved: list[ConfigField] = []
        # Loop through each field of the verifier addon
        fields: list[ConfigField] = addon.get_config_fields()
        for field in fields:
            new_field: ConfigField = self._resolve_config_field(
                field, f"{addons_prefix}{addon.name}"
            )
            fields_resolved.append(new_field)
        return fields_resolved

    def _resolve_config_field(self, field: ConfigField, prefix: str):
        """Resolve the name of each field by prefixing it with the component name.
        Returns a new config field with the name resolved to the prefix
        supplied. Using inspection all the other fields are copied. The returning
        field is exactly the same as the original, aside from the resolved name."""

        # Inspect the signature of the ConfigField which is a named tuple.
        signature = inspect.signature(ConfigField)
        params: dict[str, Any] = {}
        # Iterate and capture all parameters
        for param_name, param in signature.parameters.items():
            _ = param
            match param_name:
                case "name":
                    params[param_name] = f"{prefix}.{getattr(field, param_name)}"
                case _:
                    params[param_name] = getattr(field, param_name)

        return ConfigField(**params)

    def load_addons(self, module_name: str) -> list[BaseComponent]:
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
                    # Initialize class.
                    addon: BaseComponent = exposed_class.create()
                    self._logger.debug(f"Loading addon: {exposed_class_name}")

                    # Register config with modules
                    addon.config = self._config

                    # Add to addon list.
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

    def _load_addon_config(self, addon: BaseComponent) -> None:
        """Loads the config fields defined by an addon"""

        # Load config fields
        added_field_names: set[ConfigField] = set()
        for f in self._get_addon_resolved_fields(addon):
            # Add config fields
            if f.name in added_field_names:
                raise KeyError(f"AddonLoader: field already loaded: {f.name}")
            try:
                self._config.add_config_field(f)
            except Exception:
                self._logger.error(f"failed to register config field: {f.name}")
