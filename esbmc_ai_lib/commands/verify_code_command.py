# Author: Yiannis Charalambous

from .chat_command import ChatCommand


class VerifyCodeCommand(ChatCommand):
    def __init__(self) -> None:
        super().__init__(
            command_name="verify-code",
            help_message="Verifies using context if the code works as intended.",
        )

    def execute(self) -> None:
        print("TODO")
