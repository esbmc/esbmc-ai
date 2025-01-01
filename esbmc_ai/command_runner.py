"""Contains code for managing and running built-in and addon commands."""

import re
from esbmc_ai.commands.chat_command import ChatCommand
from esbmc_ai.commands.help_command import HelpCommand


class CommandRunner:
    """Command runner manages running and storing commands. Singleton class."""

    def __new__(cls):
        if not hasattr(cls, "instance"):
            cls.instance = super(CommandRunner, cls).__new__(cls)
        return cls.instance

    def init(self, builtin_commands: list[ChatCommand]) -> "CommandRunner":
        self._builtin_commands: dict[str, ChatCommand] = {
            cmd.command_name: cmd for cmd in builtin_commands
        }
        self._addon_commands: dict[str, ChatCommand] = {}

        # Set the help command commands
        if "help" in self._builtin_commands:
            assert isinstance(self._builtin_commands["help"], HelpCommand)
            self._builtin_commands["help"].commands = list(self.commands.values())

        return self

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
    def builtin_commands_names(self) -> list[str]:
        """Returns a list of built-in command names."""
        return list(self._builtin_commands.keys())

    @property
    def addon_commands_names(self) -> list[str]:
        """Returns a list of the addon command names."""
        return list(self._addon_commands.keys())

    @property
    def addon_commands(self) -> dict[str, ChatCommand]:
        """Returns a list of the addon commands. This is a reference to the
        internal list."""
        return self._addon_commands

    @addon_commands.setter
    def addon_commands(self, value: dict[str, ChatCommand]) -> None:
        self._addon_commands = value

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
