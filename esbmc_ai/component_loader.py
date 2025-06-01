# Author: Yiannis Charalambous

"""Module contains class for keeping track and managing built-in base 
components."""


from typing import Set
import structlog
import re

from esbmc_ai.chat_command import ChatCommand
from esbmc_ai.base_component import BaseComponent
from esbmc_ai.config_field import ConfigField
from esbmc_ai.singleton import SingletonMeta
from esbmc_ai.verifiers.base_source_verifier import BaseSourceVerifier
from esbmc_ai.log_utils import LogCategories

_loaded_fields: Set[str] = set()


class ComponentLoader(metaclass=SingletonMeta):
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
        self._verifiers: dict[str, BaseSourceVerifier] = {}
        self._verifier: BaseSourceVerifier | None = None

        self._builtin_commands: dict[str, ChatCommand] = {}
        self._addon_commands: dict[str, ChatCommand] = {}

    def load_base_component_config(self, component: BaseComponent) -> None:
        """Loads the config fields of a built-in base component, should be called at
        execute."""
        from esbmc_ai.config import Config

        # Handle loading config (since this is a built-in module)
        fields: list[ConfigField] = component.get_config_fields()
        for f in fields:
            if f.name in _loaded_fields:
                continue
            _loaded_fields.add(f.name)
            Config().load_config_field(f)

    @property
    def verfifier(self) -> BaseSourceVerifier:
        """Returns the verifier that is selected."""
        assert self._verifier, "Verifier is not set..."
        return self._verifier

    @verfifier.setter
    def verifier(self, value: BaseSourceVerifier) -> None:
        assert (
            value not in self._verifiers
        ), f"Unregistered verifier set: {value.verifier_name}"
        self._verifier = value

    def add_verifier(self, verifier: BaseSourceVerifier) -> None:
        """Adds a verifier."""
        from esbmc_ai.config import Config

        self._verifiers[verifier.name] = verifier
        verifier.config = Config()

    def set_verifier_by_name(self, value: str) -> None:
        self.verifier = self._verifiers[value]

    def get_verifier(self, value: str) -> BaseSourceVerifier | None:
        return self._verifiers.get(value)

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

    @staticmethod
    def parse_command(user_prompt_string: str) -> tuple[str, list[str]]:
        """Parses a command and returns it based on the command rules outlined in
        the wiki: https://github.com/Yiannis128/esbmc-ai/wiki/User-Chat-Mode"""
        regex_pattern: str = (
            r'\s+(?=(?:[^\\"]*(?:\\.[^\\"]*)*)$)|(?:(?<!\\)".*?(?<!\\)")|(?:\\.)+|\S+'
        )
        segments: list[str] = re.findall(regex_pattern, user_prompt_string)
        parsed_array: list[str] = [segment for segment in segments if segment != " "]
        # Remove all empty spaces.
        command: str = parsed_array[0]
        command_args: list[str] = parsed_array[1:]
        return command, command_args
