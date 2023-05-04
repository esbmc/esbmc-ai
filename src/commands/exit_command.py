# Author: Yiannis Charalambous

from src.commands.chat_command import ChatCommand


class ExitCommand(ChatCommand):
    def __init__(self) -> None:
        super().__init__(
            command_name="exit",
            help_message="Exit the program.",
        )

    def execute(self) -> None:
        print("exiting...")
        exit(0)
