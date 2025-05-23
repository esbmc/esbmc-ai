"""Contains code for managing and running built-in and addon commands."""

import re
from esbmc_ai.chat_command import ChatCommand
from esbmc_ai.singleton import SingletonMeta


class CommandRunner(metaclass=SingletonMeta):
    """Command runner manages running and storing commands. Singleton class."""

    def __init__(self, builtin_commands: list[ChatCommand] = []):
        super().__init__()
        self._builtin_commands: dict[str, ChatCommand] = {
            cmd.command_name: cmd for cmd in builtin_commands
        }
        self._addon_commands: dict[str, ChatCommand] = {}

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
