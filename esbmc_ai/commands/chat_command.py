# Author: Yiannis Charalambous

"""Contains things related to chat commands."""

from abc import ABC, abstractmethod
from typing import Any, Optional

from esbmc_ai.commands.command_result import CommandResult


class ChatCommand(ABC):
    """Abstract Base Class for implementing chat commands."""

    def __init__(
        self,
        command_name: str = "",
        help_message: str = "",
        authors: str = "",
    ) -> None:
        super().__init__()
        self.command_name = command_name
        self.help_message = help_message
        self.authors = authors

    @abstractmethod
    def execute(self, **kwargs: Optional[Any]) -> Optional[CommandResult]:
        """The main entrypoint of the command. This is abstract and will need to
        be implemented."""
        raise NotImplementedError(f"Command {self.command_name} is not implemented.")
