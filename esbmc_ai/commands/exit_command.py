# Author: Yiannis Charalambous

"""Contains the exit chat command."""

import sys
from typing import Any, Optional
from typing_extensions import override

from esbmc_ai.chat_command import ChatCommand


class ExitCommand(ChatCommand):
    """Used to exit user chat mode gracefully."""

    def __init__(self) -> None:
        super().__init__(
            command_name="exit",
            help_message="Exit the program.",
        )

    @override
    def execute(self) -> None:
        print("exiting...")
        sys.exit(0)
