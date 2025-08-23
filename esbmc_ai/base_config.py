# Author: Yiannis Charalambous 2023

"""ABC Config that can be used to load config files."""

from abc import ABC
import sys
from pathlib import Path, PurePath
from platform import system as system_name
import tomllib as toml
from typing import (
    Any,
    Callable,
    Dict,
    List,
)
import re 

from esbmc_ai.config_field import ConfigField


class BaseConfig(ABC):
    """Config loader for ESBMC-AI"""

    def __init__(self) -> None:
        super().__init__()
        self._fields: List[ConfigField] = []
        self._values: Dict[str, Any] = {}
        self.original_config_file: dict[str, Any]
        self.config_file: dict[str, Any]
        self.on_load_value: list[Callable[[str], None]] = []

    def load_config_fields(self, cfg_path: Path, fields: list[ConfigField],cfg:PurePath) -> None:
        """Initializes the base config structures. Loads the config file and fields."""  
        #match the system name to ensure backslashes in windows are handled
        match system_name():
            case "Windows":
                #dictionary to map hex escape sequences to their literal representations
                hex_dict={"\x0a":"\\n",
                          "\x09":"\\t",
                          "\x0d":"\\r",
                          "\x0b":"\\v",
                          "\x08":"\\b",
                          "\x0c":"\\f",
                          "\x07":"\\a",
                          }  
                try:
                    hex_str=str(cfg).split("\\")#split the pure path cfg to view the escaped charachters
                    clean_str=[]#a second list to hold the corrected string
                    for s in hex_str:
                        decoded_str=s
                        for hex_rep,letter in hex_dict.items():
                            #replace hexadecimal representations in the filepath
                            decoded_str=s.replace(hex_rep,letter)
                        clean_str.append(decoded_str)
                    cfg_path=Path("\\".join(clean_str)) #corrected path as a WindowsPath
                except Exception as e:
                    print(f"{cfg} is the pure path, exception:{e} occured")
                if not (cfg_path.exists() and cfg_path.is_file()):
                    print(f"Error: Config not found: {cfg_path}")
                    sys.exit(1)

            case "Linux"|"Darwin":
                if not (cfg_path.exists() and cfg_path.is_file()):
                    print(f"Error: Config not found: {cfg_path}")
                    sys.exit(1)

        with open(cfg_path, "r") as file:
            self.original_config_file = toml.loads(file.read())

        # Flatten dict as the _fields are defined in a flattened format for
        # convenience.
        self.config_file = self.flatten_dict(self.original_config_file)

        # Load all the config file field entries
        for field in fields:
            self.load_config_field(field)

    def load_config_field(self, field: ConfigField) -> None:
        """Loads a new field from the config. Init needs to be called before
        calling this to initialize the base config."""
        if field not in self._fields:
            self._fields.append(field)

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

    def set_custom_field(self, field: ConfigField, value: Any) -> None:
        """Loads a new field from a custom source. Still validates the value given
        to it."""
        # Check if None and not allowed!
        if (
            field.default_value is None
            and not field.default_value_none
            and value is None
        ):
            raise ValueError(
                f"Failed to add field from custom source: {field.name} has a "
                "None value when it can't be"
            )

        # Validate field
        if not field.validate(value):
            msg = f"Field: {field.name} is invalid: {value}"
            if field.get_error_message is not None:
                msg += ": " + field.get_error_message(value)
            elif field.error_message:
                msg += ": " + field.error_message
            raise ValueError(f"Config loading error: {msg}")

        if field not in self._fields:
            self._fields.append(field)
        self._values[field.name] = field.on_load(value)

    def get_value(self, name: str) -> Any:
        """Gets the value of key name"""
        for cb in self.on_load_value:
            cb(name)
        return self._values[name]

    def set_value(self, name: str, value: Any) -> None:
        """Sets a value in the config, if it does not exist, it will create one.
        This uses toml notation dot notation to namespace the elements."""
        self._values[name] = value

    def contains_field(self, name: str) -> bool:
        """Check if config has a field."""
        return any(name == field.name for field in self._fields)

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
