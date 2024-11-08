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

    def init(self, builtin_commands: list[ChatCommand]) -> None:
        self._builtin_commands: list[ChatCommand] = builtin_commands.copy()
        self._addon_commands: list[ChatCommand] = []

        # Set the help command commands
        for cmd in self._builtin_commands:
            if cmd.command_name == "help":
                assert isinstance(cmd, HelpCommand)
                cmd.commands = self.commands

    @property
    def commands(self) -> list[ChatCommand]:
        """Returns all commands. The list is copied."""
        return self._builtin_commands + self._addon_commands

    @property
    def command_names(self) -> list[str]:
        """Returns a list of built-in commands. This is a reference to the
        internal list."""
        return [cmd.command_name for cmd in self.commands]

    @property
    def builtin_commands_names(self) -> list[str]:
        """Returns a list of built-in command names."""
        return [cmd.command_name for cmd in self._builtin_commands]

    @property
    def addon_commands_names(self) -> list[str]:
        """Returns a list of the addon command names."""
        return [cmd.command_name for cmd in self._addon_commands]

    @property
    def addon_commands(self) -> list[ChatCommand]:
        """Returns a list of the addon commands. This is a reference to the
        internal list."""
        return self._addon_commands

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
