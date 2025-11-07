# Author: Yiannis Charalambous

"""Contains things related to chat commands."""

from abc import abstractmethod
from typing import Any, override

from esbmc_ai.base_component import BaseComponent
from esbmc_ai.command_result import CommandResult
from esbmc_ai.log_utils import LogCategories


class ChatCommand(BaseComponent):
    """Abstract Base Class for implementing chat commands."""

    @override
    @classmethod
    def create(cls) -> "BaseComponent":
        obj: BaseComponent = super().create()
        obj._logger = obj.logger.bind(category=LogCategories.COMMAND)
        return obj

    def __init__(
        self,
        command_name: str = "",
        authors: str = "",
        help_message: str = "",
    ) -> None:
        super().__init__()
        self._name = command_name
        self._authors = authors

        self.help_message = help_message

    @property
    def command_name(self) -> str:
        """Alias for name"""
        return self.name

    @abstractmethod
    def execute(self) -> CommandResult | None:
        """The main entrypoint of the command. This is abstract and will need to
        be implemented."""
        raise NotImplementedError(f"Command {self.command_name} is not implemented.")
