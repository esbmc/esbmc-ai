# Author: Yiannis Charalambous

"""This module can be used by other modules to declare config entries."""

from typing import (
    Any,
    Callable,
    NamedTuple,
    Optional,
)


class ConfigField(NamedTuple):
    """Represents a loadable entry in the config."""

    name: str
    """The name of the config field and also namespace"""
    default_value: Any
    """If a default value is supplied, then it can be omitted from the config.
    In order to have a "None" default value, default_value_none must be set."""
    default_value_none: bool = False
    """If true, then the default value will be None, so during
    validation, if no value is supplied, then None will be the
    the default value, instead of failing due to None being the
    default value which under normal circumstances means that the
    field is not optional."""
    validate: Callable[[Any], bool] = lambda _: True
    """Lambda function to validate if field has a valid value.
    Default is identity function which is return true."""
    on_load: Callable[[Any], Any] = lambda v: v
    """Transform the value once loaded, this allows the value to be saved
    as a more complex type than that which is represented in the config
    file.
    
    Is ignored if on_read is defined."""
    on_read: Optional[Callable[[dict[str, Any]], Any]] = None
    """If defined, will be called and allows to custom load complex types that
    may not match 1-1 in the config. The config file passed as a parameter here
    is the original, unflattened version. The value returned should be the value
    assigned to this field.
    
    This is a more versatile version of on_load. So if this is used, the on_load
    will be ignored."""
    error_message: Optional[str] = None
    """Optional string to provide a generic error message."""
    get_error_message: Optional[Callable[[Any], str]] = None
    """Optionsl function to get more verbose output than error_message."""
