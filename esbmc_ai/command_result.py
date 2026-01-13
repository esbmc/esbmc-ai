# Author: Yiannis Charalambous

"""Contains the base class for chat command results."""

from pydantic import BaseModel, ConfigDict


class CommandResult(BaseModel):
    """Base class for the return result of chat commands.

    Uses Pydantic BaseModel for automatic serialization to JSON.
    Subclasses should define their fields as Pydantic model fields.
    """

    successful: bool
    """True if the execution of the command was successful, False otherwise."""

    def to_json(self, indent: int = 2) -> str:
        """Serialize the result to JSON string.

        Args:
            indent: Number of spaces for indentation (default: 2)

        Returns:
            JSON string representation of the result
        """
        return self.model_dump_json(indent=indent)

    def __str__(self) -> str:
        return "Command returned " + (
            "successful" if self.successful else "unsuccessful"
        )
