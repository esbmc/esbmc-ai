# Author: Yiannis Charalambous

from abc import ABC, abstractmethod
from typing import Any, Optional

from esbmc_ai.commands.command_result import CommandResult


class ChatCommand(ABC):
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
        raise NotImplementedError(f"Command {self.command_name} is not implemented.")
