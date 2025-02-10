# Author: Yiannis Charalambous

"""Contains things related to chat commands."""

from abc import abstractmethod
from typing import Any

from esbmc_ai.base_component import BaseComponent
from esbmc_ai.commands.command_result import CommandResult


class ChatCommand(BaseComponent):
    """Abstract Base Class for implementing chat commands."""

    def __init__(
        self,
        command_name: str = "",
        help_message: str = "",
        authors: str = "",
    ) -> None:
        super().__init__(name=command_name, authors=authors)

        self.help_message = help_message

    @property
    def command_name(self) -> str:
        """Alias for name"""
        return self.name

    @abstractmethod
    def execute(self, **kwargs: Any | None) -> CommandResult | None:
        """The main entrypoint of the command. This is abstract and will need to
        be implemented."""
        raise NotImplementedError(f"Command {self.command_name} is not implemented.")
