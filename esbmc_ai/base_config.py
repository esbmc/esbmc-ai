# Author: Yiannis Charalambous 2023

"""ABC Config that can be used to load config files."""

from abc import ABC
import sys
from pathlib import Path
import tomllib as toml
from typing import (
    Any,
    Dict,
    List,
)

from esbmc_ai.config_field import ConfigField

default_scenario: str = "base"


class BaseConfig(ABC):
    """Config loader for ESBMC-AI"""

    def __init__(self) -> None:
        super().__init__()
        self._fields: List[ConfigField]
        self._values: Dict[str, Any]
        self.cfg_path: Path
        self.original_config_file: dict[str, Any]
        self.config_file: dict[str, Any]

    def base_init(self, cfg_path: Path, fields: list[ConfigField]) -> None:
        """Initializes the base config structures. Loads the config file and fields."""
        self._fields = fields
        self._values = {}

        self.cfg_path = cfg_path

        if not (self.cfg_path.exists() and self.cfg_path.is_file()):
            print(f"Error: Config not found: {self.cfg_path}")
            sys.exit(1)

        with open(self.cfg_path, "r") as file:
            self.original_config_file = toml.loads(file.read())

        # Flatten dict as the _fields are defined in a flattened format for
        # convenience.
        self.config_file = self.flatten_dict(self.original_config_file)

        # Load all the config file field entries
        for field in self._fields:
            self.add_config_field(field)

    def add_config_field(self, field: ConfigField) -> None:
        """Loads a new field from the config. Init needs to be called before
        calling this to initialize the base config."""

        # If on_read is overwritten, then the reading process is manually
        # defined so fallback to that.
        if field.on_read:
            self._values[field.name] = field.on_read(self.original_config_file)
            return

        # Proceed to default read

        # Is field entry found in config?
        if field.name in self.config_file:
            # Check if None and not allowed!
            if (
                field.default_value is None
                and not field.default_value_none
                and self.config_file[field.name] is None
            ):
                raise ValueError(
                    f"The config entry {field.name} has a None value when it can't be"
                )

            # Validate field
            if not field.validate(self.config_file[field.name]):
                msg = f"Field: {field.name} is invalid: {self.config_file[field.name]}"
                if field.get_error_message is not None:
                    msg += ": " + field.get_error_message(self.config_file[field.name])
                elif field.error_message:
                    msg += ": " + field.error_message
                raise ValueError(f"Config loading error: {msg}")

            # Assign field from config file
            self._values[field.name] = field.on_load(self.config_file[field.name])
        elif field.default_value is None and not field.default_value_none:
            raise KeyError(f"{field.name} is missing from config file")
        else:
            # Use default value
            self._values[field.name] = field.default_value

    def get_value(self, name: str) -> Any:
        """Gets the value of key name"""
        return self._values[name]

    def set_value(self, name: str, value: Any) -> None:
        """Sets a value in the config, if it does not exist, it will create one.
        This uses toml notation dot notation to namespace the elements."""
        self._values[name] = value

    @classmethod
    def flatten_dict(cls, d, parent_key="", sep="."):
        """Recursively flattens a nested dictionary."""
        items = {}
        for k, v in d.items():
            new_key = parent_key + sep + k if parent_key else k
            if isinstance(v, dict):
                items.update(cls.flatten_dict(v, new_key, sep=sep))
            else:
                items[new_key] = v
        return items
