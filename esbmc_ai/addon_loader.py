# Author: Yiannis Charalambous

"""This module contains code regarding configuring and loading addon modules."""

from typing import Any
from typing_extensions import Optional, override
import importlib
from importlib.util import find_spec
from importlib.machinery import ModuleSpec
import sys

from esbmc_ai.base_config import BaseConfig
from esbmc_ai.command_runner import ChatCommand
from esbmc_ai.logging import printv
from esbmc_ai.verifier_runner import BaseSourceVerifier
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

    def init(self, config: Config, builtin_verifier_names: list[str]):
        """Call to initialize the addon loader. It will load the addons and
        register them with the command runner and verifier runner."""

        self.base_init(config.cfg_path, [])

        self._config: Config = config

        # Register field with Config to know which modules to load. This will
        # load them automatically.
        config.add_config_field(
            ConfigField(
                name="addon_modules",
                default_value=[],
                validate=self._validate_addon_modules,
                on_load=self._init_addon_modules,
                error_message="addon_modules must be a list of Python modules to load",
            ),
        )

        self.chat_command_addons: dict[str, ChatCommand] = {}
        self.verifier_addons: dict[str, BaseSourceVerifier] = {}

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

        # Init the verifier.name field for the main config
        self._config.add_config_field(
            ConfigField(
                name="verifier.name",
                default_value="esbmc",
                validate=lambda v: isinstance(v, str)
                and v in self.verifier_addon_names + builtin_verifier_names,
                error_message="Invalid verifier name specified.",
            )
        )

    @property
    def chat_command_addon_names(self) -> list[str]:
        return list(self.chat_command_addons.keys())

    @property
    def verifier_addon_names(self) -> list[str]:
        return list(self.verifier_addons.keys())

    def _load_chat_command_addons(self) -> None:
        self.chat_command_addons.clear()

        for m in self._config.get_value("addon_modules"):
            if isinstance(m, ChatCommand):
                self.chat_command_addons[m.command_name] = m

        # Init config fields
        for field in self._get_chat_command_addon_fields():
            self.add_config_field(field)

        if len(self.chat_command_addons) > 0:
            printv(
                "ChatCommand Addons:\n\t* "
                + "\t * ".join(self.chat_command_addon_names)
            )

    def _load_verifier_addons(self) -> None:
        """Loads the verifier addons, initializes their config fields."""
        self.verifier_addons.clear()
        for m in self._config.get_value("addon_modules"):
            if isinstance(m, BaseSourceVerifier):
                self.verifier_addons[m.verifier_name] = m

        # Init config fields
        for field in self._get_verifier_addon_fields():
            self.add_config_field(field)

        if len(self.verifier_addons) > 0:
            printv(
                "Verifier Addons:\n\t* "
                + "\t * ".join(list(self.verifier_addons.keys()))
            )

    def _validate_addon_modules(self, mods: list[str]) -> bool:
        """Validates that all values are string."""
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
        from esbmc_ai.commands.chat_command import ChatCommand
        from esbmc_ai.verifiers import BaseSourceVerifier
        from esbmc_ai.testing.base_tester import BaseTester

        allowed_types = ChatCommand | BaseSourceVerifier | BaseTester

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
                print(f"Addon Loader: Could not import module: {module_name}: {e}")
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
        # Resolve the name of each field by prefixing it with the verifier name.
        # Create a new config field with the new name.
        new_field = ConfigField(
            name=f"{prefix}.{field.name}",
            default_value=field.default_value,
            default_value_none=field.default_value_none,
            validate=field.validate,
            on_load=field.on_load,
            on_read=field.on_read,
            error_message=field.error_message,
        )

        return new_field

    def _get_chat_command_addon_fields(self) -> list[ConfigField]:
        """Adds each chat command's config fields to the config. After resolving
        each chat command's config fields to their namespace."""
        # If an addon prefix is defined, then add a .
        addons_prefix: str = (
            AddonLoader.addon_prefix + "." if AddonLoader.addon_prefix else ""
        )
        fields_resolved: list[ConfigField] = []
        # Loop through verifier addons
        for cmd in self.chat_command_addons.values():
            # Loop through each field of the verifier addon
            fields: list[ConfigField] = cmd.get_config_fields()
            for field in fields:
                new_field: ConfigField = self._resolve_config_field(
                    field, f"{addons_prefix}{cmd.command_name}"
                )
                fields_resolved.append(new_field)
        return fields_resolved

    def _get_verifier_addon_fields(self) -> list[ConfigField]:
        """Adds each verifier's config fields to the config. After resolving
        each verifier's config fields to their namespace."""
        # If an addon prefix is defined, then add a .
        addons_prefix: str = (
            AddonLoader.addon_prefix + "." if AddonLoader.addon_prefix else ""
        )
        fields_resolved: list[ConfigField] = []
        # Loop through verifier addons
        for verifier in self.verifier_addons.values():
            # Loop through each field of the verifier addon
            fields: list[ConfigField] = verifier.get_config_fields()
            for field in fields:
                new_field: ConfigField = self._resolve_config_field(
                    field, f"{addons_prefix}{verifier.verifier_name}"
                )
                fields_resolved.append(new_field)
        return fields_resolved
