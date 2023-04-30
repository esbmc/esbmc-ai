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


class LoadingWidget(object):
    done: bool = False
    thread: Thread
    loading_text: str
    anim_speed: float = 0.1

    def __init__(self, anim_speed: float = 0.1) -> None:
        super().__init__()
        self.anim_speed = anim_speed

    def _animate(self) -> None:
        for c in cycle(["|", "/", "-", "\\"]):
            if self.done:
                break
            terminal.write(f"\r{self.loading_text} " + c)
            terminal.flush()
            sleep(self.anim_speed)
        terminal.write("\r" + " " * (len(self.loading_text) + 2))
        terminal.flush()
        terminal.write("\r")
        terminal.flush()

    def start(self, text: str = "Please Wait") -> None:
        self.done = False
        self.loading_text = text
        self.thread = Thread(target=self._animate)
        self.thread.daemon = True
        self.thread.start()

    def stop(self) -> None:
        self.done = True
        # Block until end.
        self.thread.join()
