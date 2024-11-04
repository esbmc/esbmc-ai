# Author: Yiannis Charalambous

"""Contains the base class for chat command results."""

from abc import ABC, abstractmethod


class CommandResult(ABC):
    """Base class for the return result of chat commands."""

    @property
    @abstractmethod
    def successful(self) -> bool:
        """Returns true if the execution of the command was successful. False if
        otherwise. If false, then it is up to the command to provide a method to
        access the reason."""
        raise NotImplementedError()

    def __str__(self) -> str:
        return "Command returned " + (
            "successful" if self.successful else "unsuccessful"
        )
