# Author: Yiannis Charalambous

from abc import abstractmethod


class CommandResult:
    @property
    @abstractmethod
    def successful(self) -> bool:
        raise NotImplementedError()

    def __str__(self) -> str:
        return f"Command returned " + (
            "successful" if self.successful else "unsuccessful"
        )
