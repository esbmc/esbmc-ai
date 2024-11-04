# Author: Yiannis Charalambous 2023

"""
  This program is designed to create
  and animate a simple loading animation.
  Original source: https://gist.github.com/rudrathegreat/b11daed176c8119dcedbb6b06c953590
"""

from sys import stdout as terminal
from time import sleep
from itertools import cycle
from threading import Thread
from typing import Optional
from typing_extensions import override


class BaseLoadingWidget:
    """Base loading widget, will not display any information."""

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        _ = exc_type
        _ = exc_val
        _ = exc_tb
        self.stop()

    def __call__(self, text: Optional[str] = None):
        _ = text
        return self

    def start(self, text: str = "") -> None:
        _ = text

    def stop(self) -> None:
        pass


class LoadingWidget(BaseLoadingWidget):
    """Loading widget that can display an animation along with some text."""

    done: bool = False
    thread: Optional[Thread]
    loading_text: str
    animation: list[str]
    anim_speed: float
    anim_clear_length: int

    def __init__(
        self,
        anim_speed: float = 0.1,
        animation: list[str] = ["|", "/", "-", "\\"],
    ) -> None:
        super().__init__()
        self.anim_speed = anim_speed
        self.animation = animation

        # Find the largest animatioon
        self.anim_clear_length = 0
        for frame in self.animation:
            if len(frame) > self.anim_clear_length:
                self.anim_clear_length = len(frame)

    def __call__(self, text: Optional[str] = None):
        """Allows you to set the text in a with statement easily."""
        if text:
            self.loading_text = text
        return self

    def _animate(self) -> None:
        for c in cycle(self.animation):
            if self.done:
                break
            # Calculate how much extra space to clear after c.
            extra_space_clear: int = self.anim_clear_length - len(c)
            terminal.write(f"\r{self.loading_text} " + c + " " * extra_space_clear)
            terminal.flush()
            sleep(self.anim_speed)

        # +1 for space between loading text and c.
        clear_length: int = len(self.loading_text) + 1 + self.anim_clear_length
        terminal.write("\r" + " " * clear_length)
        terminal.flush()
        terminal.write("\r")
        terminal.flush()

    @override
    def start(self, text: str = "Please Wait") -> None:
        self.done = False
        self.loading_text = text
        self.thread = Thread(target=self._animate)
        self.thread.daemon = True
        self.thread.start()

    @override
    def stop(self) -> None:
        self.done = True
        # Block until end.
        if self.thread:
            self.thread.join()
