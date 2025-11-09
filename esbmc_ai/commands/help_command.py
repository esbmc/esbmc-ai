# Author: Yiannis Charalambous

"""Contains the help command."""

from typing import Any
from typing_extensions import override

from esbmc_ai.chat_command import ChatCommand
from esbmc_ai.component_manager import ComponentManager


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
    def execute(self) -> Any:
        print("Commands:")
        for command in ComponentManager().builtin_commands.values():
            print(f"* {command.command_name}: {command.help_message}")
            if command.authors:
                print(f"\tAuthors: {command.authors}")

        if ComponentManager().addon_commands:
            print("\nAddon Commands:")
        else:
            self.logger.info("No addon commands to show...")
        for command in ComponentManager().addon_commands.values():
            print(f"* {command.command_name}: {command.help_message}")
            if command.authors:
                print(f"\tAuthors: {command.authors}")

        print("\nLicense:")
        print("* ESBMC-AI is dual-licensed (AGPL-3.0 / Commercial)")
        print("* Run 'esbmc-ai license' for full details")
