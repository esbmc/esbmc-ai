# Author: Yiannis Charalambous

"""Contains the help command."""

from typing import Any
from typing_extensions import override

from esbmc_ai.chat_command import ChatCommand


class HelpCommand(ChatCommand):
    """Command that prints helpful information about other commands. Including
    addon commands."""

    commands: list[ChatCommand] = []

    def __init__(self) -> None:
        super().__init__(
            command_name="help",
            help_message="Print this help message.",
        )

    @override
    def execute(self, **_: Any) -> Any:
        print("Commands:")

        for command in self.commands:
            print(f"* {command.command_name}: {command.help_message}")
            if command.authors:
                print(f"\tAuthors: {command.authors}")

        print()
        print("User Chat Mode Prompts:")
        print("1) What is the exact error?")
        print("2) Please explain the error to me.")
        print("3) What is the cause of this error?")
