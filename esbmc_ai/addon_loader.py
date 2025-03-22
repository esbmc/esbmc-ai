# Author: Yiannis Charalambous

"""This module contains code regarding configuring and loading addon modules."""

import inspect
from typing import Any, override
import traceback
import sys
import importlib
from importlib.util import find_spec
from importlib.machinery import ModuleSpec
from typing_extensions import Optional

from esbmc_ai.base_component import BaseComponent
from esbmc_ai.base_config import BaseConfig
from esbmc_ai.commands.chat_command import ChatCommand
from esbmc_ai.logging import printv
from esbmc_ai.verifiers.base_source_verifier import BaseSourceVerifier
from esbmc_ai.config import Config, ConfigField


class AddonLoader(BaseConfig):
    """The addon loader manages loading addon modules. This includes:
    * Managing the config fields of the addons.
    * Binding the loaded addons with CommandRunner and VerifierRunner.

    It hooks into the main config loader and adds config fields for selecting
    the modules. Additionally it behaves like a config loader, this is because
    it puts all the configs that the addons use into a namespace called "addons".

    The exception to this are the built-in modules which directly hook into the
    main config object.
    """

    addon_prefix: str = "addons"

    def __new__(cls):
        if not hasattr(cls, "instance"):
            cls.instance = super(AddonLoader, cls).__new__(cls)
        return cls.instance

    _config: Config
    chat_command_addons: dict[str, ChatCommand] = {}
    verifier_addons: dict[str, BaseSourceVerifier] = {}

    def init(self, config: Config, builtin_verifier_names: list[str]):
        """Call to initialize the addon loader. It will load the addons and
        register them with the command runner and verifier runner."""

        self.base_init(config.cfg_path, [])

        self._config = config

        # Ensure the current directory is in sys.path in order for relative
        # addon modules to be imported (used for dev purposes).
        if self._config.get_value("dev_mode") and "" not in sys.path:
            sys.path.insert(0, "")

        # Register field with Config to know which modules to load. This will
        # load them automatically.
        config.add_config_field(
            ConfigField(
                name="addon_modules",
                default_value=[],
                validate=self._validate_addon_modules,
                on_load=self._init_addon_modules,
                error_message="addon_modules must be a list of Python modules to load",
                help_message="The addon modules to load during startup. Additional "
                "modules may be loaded by the specified modules as dependencies.",
            ),
        )

        # Load all the addon commands
        self._load_chat_command_addons()

        # Load all the addon verifiers
        self._load_verifier_addons()

        # Register config with modules
        for mod in (self.chat_command_addons | self.verifier_addons).values():
            mod.config = self

        # Ensure no duplicates
        field_names: list[str] = []
        for f in self._fields + self._config._fields:
            if f.name in field_names:
                raise KeyError(f"Field is redefined: {f.name}")
            field_names.append(f.name)
        del field_names

        # Init the verifier.name field for the main config. The reason this is
        # not part of the main config is that verifiers are treated as addons,
        # even internally.
        self._config.add_config_field(
            ConfigField(
                name="verifier.name",
                default_value="esbmc",
                validate=lambda v: isinstance(v, str)
                and v in self.verifier_addon_names + builtin_verifier_names,
                error_message="Invalid verifier name specified.",
                help_message="The verifier to use. Default is ESBMC.",
            )
        )

    @property
    def chat_command_addon_names(self) -> list[str]:
        """Returns all the addon chat command names."""
        return list(self.chat_command_addons.keys())

    @property
    def verifier_addon_names(self) -> list[str]:
        """Returns all the addon verifier names."""
        return list(self.verifier_addons.keys())

    def _load_chat_command_addons(self) -> None:
        self.chat_command_addons.clear()

        for m in self._config.get_value("addon_modules"):
            if isinstance(m, ChatCommand):
                self.chat_command_addons[m.command_name] = m

        # Init config fields
        for field in self._get_addons_fields(list(self.chat_command_addons.values())):
            try:
                self.add_config_field(field)
            except Exception:
                print(f"AddonLoader: Failed to register config field: {field.name}")
                raise

        if len(self.chat_command_addons) > 0:
            printv(
                "ChatCommand Addons:\n"
                + "\n".join(f"\t* {cm}" for cm in self.chat_command_addon_names),
            )

    def _load_verifier_addons(self) -> None:
        """Loads the verifier addons, initializes their config fields."""
        self.verifier_addons.clear()
        for m in self._config.get_value("addon_modules"):
            if isinstance(m, BaseSourceVerifier):
                self.verifier_addons[m.verifier_name] = m

        # Init config fields
        for field in self._get_addons_fields(list(self.verifier_addons.values())):
            self.add_config_field(field)

        if len(self.verifier_addons) > 0:
            printv(
                "Verifier Addons:\n"
                + "".join(f"\t* {k}" for k in self.verifier_addons.keys())
            )

    def _validate_addon_modules(self, mods: list[str]) -> bool:
        """Validates that all values are string and that the module exists."""
        for m in mods:
            if not isinstance(m, str):
                return False
            spec: Optional[ModuleSpec] = find_spec(m)
            if spec is None:
                return False
        return True

    def _init_addon_modules(self, mods: list[str]) -> list:
        """Will import addon modules that exist and iterate through the exposed
        attributes, will then get all available exposed classes and store them.

        This method will load classes:
        * ChatCommands
        * BaseSourceVerifier"""

        allowed_types = ChatCommand | BaseSourceVerifier

        result: list = []
        for module_name in mods:
            try:
                m = importlib.import_module(module_name)
                for attr_name in getattr(m, "__all__"):
                    # Get the class
                    attr_class = getattr(m, attr_name)
                    # Check if valid addon type and import
                    if issubclass(attr_class, allowed_types):
                        # Initialize class.
                        result.append(attr_class())
                        printv(f"Loading addon: {attr_name}")
            except ModuleNotFoundError as e:
                print("Addon Loader: Error while loading module: Traceback:")
                traceback.print_tb(e.__traceback__)
                print(f"Addon Loader: Could not import module: {module_name}: {e}")
                sys.exit(1)
            except AttributeError as e:
                print(f"Addon Loader: Module {module_name} is invalid: {e}")
                sys.exit(1)

        return result

    @override
    def get_value(self, name: str) -> Any:
        """Searches first for a config value in the addon config, if it is
        not found, searches the global.

        How does it determine if a config field is part of the addon defined
        fields? Well the AddonConfig class will add a prefix followed by the
        name of the verifier."""

        # Check if it references an addon.
        split_key: list[str] = name.split(".")
        if split_key[0] == AddonLoader.addon_prefix:
            if (
                split_key[1]
                in self.chat_command_addon_names + self.verifier_addon_names
            ):
                # Check if key exists.
                if name in self._values:
                    return super().get_value(name)
                else:
                    raise KeyError(f"Key: {name} not in AddonConfig")
        # If the key is not in the addon prefix, then get from global config.
        return self._config.get_value(name)

    def _resolve_config_field(self, field: ConfigField, prefix: str):
        """Resolve the name of each field by prefixing it with the verifier name.
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

    def _get_addons_fields(self, addons: list[BaseComponent]) -> list[ConfigField]:
        """Returns each addons's config fields. After resolving each field to
        their namespace using the name of the component."""
        # If an addon prefix is defined, then add a .
        addons_prefix: str = (
            AddonLoader.addon_prefix + "." if AddonLoader.addon_prefix else ""
        )
        fields_resolved: list[ConfigField] = []
        # Loop through verifier addons
        for addon in addons:
            # Loop through each field of the verifier addon
            fields: list[ConfigField] = addon.get_config_fields()
            for field in fields:
                new_field: ConfigField = self._resolve_config_field(
                    field, f"{addons_prefix}{addon.name}"
                )
                fields_resolved.append(new_field)
        return fields_resolved
