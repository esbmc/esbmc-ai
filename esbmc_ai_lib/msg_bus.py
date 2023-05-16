# Author: Yiannis Charalambous

from typing import Callable


class Signal(object):
    subscribers: list[Callable] = []

    def add_listener(self, fn: Callable) -> None:
        self.subscribers.append(fn)

    def remove_listener(self, fn: Callable) -> None:
        self.subscribers.remove(fn)

    def emit(self, *args, **params) -> None:
        for sub in self.subscribers:
            sub(*args, **params)
