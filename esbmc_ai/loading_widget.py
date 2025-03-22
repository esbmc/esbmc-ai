# Author: Yiannis Charalambous 2023

"""
  This program is designed to create and animate a simple loading animation.
  Original source: https://gist.github.com/rudrathegreat/b11daed176c8119dcedbb6b06c953590
"""

import sys

from time import sleep
from itertools import cycle
from threading import Thread
from types import TracebackType
from typing import Any, AnyStr, BinaryIO, TextIO
from typing_extensions import override
from blessed import Terminal


class BaseLoadingWidget:
    """Base loading widget, will not display any information."""

    @property
    def is_running(self) -> bool:
        """Is the loading animation playing?"""
        return False

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        _ = exc_type
        _ = exc_val
        _ = exc_tb
        self.stop()

    def __call__(self, text: str | None = None):
        _ = text
        return self

    def start(self, text: str = "") -> None:
        """Starts the animation."""
        _ = text

    def stop(self) -> None:
        """Stops the animation."""


class _StdoutInterceptor(TextIO):
    """Intercepts writes to sys.stdout so that printing clears and redraws the widget."""

    def __init__(self, original: TextIO, widget: BaseLoadingWidget) -> None:
        self.original: TextIO = original
        self.widget: BaseLoadingWidget = widget

    @override
    def write(self, text: AnyStr) -> int:
        """Clears the loading widget before writing."""
        # Clear the widget line before writing new text.
        was_running: bool = self.widget.is_running
        if was_running:
            self.widget.stop()

        # Print the text
        result: int = self.original.write(str(text))

        # After printing, redraw the widget if it's still active.
        if was_running:
            self.widget.start()

        return result

    @override
    def __enter__(self) -> TextIO:
        return self.original.__enter__()

    @override
    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
        /,
    ) -> None:
        return self.original.__exit__(exc_type, exc_val, exc_tb)

    @property
    @override
    def buffer(self) -> BinaryIO:
        return self.original.buffer

    @property
    @override
    def errors(self) -> str | None:
        return self.original.errors

    @property
    @override
    def line_buffering(self) -> int:
        return self.original.line_buffering

    @property
    @override
    def newlines(self) -> Any:
        return self.original.newlines

    @property
    @override
    def encoding(self) -> str:
        return self.original.encoding

    @override
    def flush(self) -> None:
        """Calls flush on the original stream."""
        return self.original.flush()


loading_widget_anim_1: list[str] = [
    "[          ]",
    "[          ]",
    "[==        ]",
    "[===       ]",
    "[====      ]",
    "[=====     ]",
    "[======    ]",
    "[=======   ]",
    "[========  ]",
    "[========= ]",
    "[==========]",
    "[ =========]",
    "[  ========]",
    "[   =======]",
    "[    ======]",
    "[     =====]",
    "[      ====]",
    "[       ===]",
    "[        ==]",
    "[         =]",
]

loading_widget_anim_2: list[str] = [
    "[ Loading ]",
    "[ Loading ]",
    "[ Loading ]",
    "[ Loading ]",
    "[ Loading ]",
    "[=Loading ]",
    "[==oading ]",
    "[===ading ]",
    "[====ding ]",
    "[=====ing ]",
    "[======ng ]",
    "[=======g ]",
    "[======== ]",
    "[=========]",
    "[ ========]",
    "[ L=======]",
    "[ Lo======]",
    "[ Loa=====]",
    "[ Load====]",
    "[ Loadi===]",
    "[ Loadin==]",
    "[ Loading=]",
    "[ Loading ]",
    "[ Loading ]",
    "[ Loading ]",
    "[ Loading ]",
    "[ Loading ]",
]

loading_widget_anim_3: list[str] = [
    " [=     ]",
    " [ =    ]",
    " [  =   ]",
    " [   =  ]",
    " [    = ]",
    " [     =]",
    " [    = ]",
    " [   =  ]",
    " [  =   ]",
    " [ =    ]",
]

loading_widget_anim_4: list[str] = [
    "     <>",
    "    <==>",
    "   <====>",
    "  <======>",
    " <========>",
    "<==========>",
]

loading_widget_anim_5: list[str] = [
    "     <>",
    "    <==>",
    "   <====>",
    "  <======>",
    " <========>",
    "<==========>",
    " <========>",
    "  <======>",
    "   <====>",
    "    <==>",
]


class LoadingWidget(BaseLoadingWidget):
    """Loading widget that can display an animation along with some text.

    * anim_speed: Delay in seconds between each frame.
    * ephemeral: True to print the message on screen after animation stops."""

    def __init__(
        self,
        anim_speed: float = 0.1,
        ephemeral: bool = False,
        animation: list[str] | None = None,
    ) -> None:
        super().__init__()
        self.anim_speed: float = anim_speed
        self.animation: list[str] = animation if animation else ["|", "/", "-", "\\"]
        self.ephemeral: bool = ephemeral
        self.loading_text: str
        self._running: bool = False
        self._terminal: Terminal = Terminal()

        # Multi-threading
        self.thread: Thread | None = None
        self._interceptor: _StdoutInterceptor = _StdoutInterceptor(sys.stdout, self)

        # Find the largest frame in the animatioon
        self.anim_clear_length: int = max(len(frame) for frame in self.animation)

    @property
    @override
    def is_running(self) -> bool:
        return self._running

    def __call__(self, text: str | None = None):
        """Allows you to set the text in a with statement easily."""
        if text:
            self.loading_text = text
        return self

    def _animate(self) -> None:
        """We use the original stdout stream because if we call stdout in here
        we will go into the StdoutInterceptor, if that happens during
        thread.join(), then stop() will be called in the write() of interceptor
        and then that will cause a crash because a thread can't call join on
        itself."""
        text: str = ""
        for c in cycle(self.animation):
            if not self._running:
                # Clear drawn text
                self._interceptor.original.write(
                    " " * len(text) + self._terminal.move_left(len(text)),
                )
                if self.ephemeral:
                    self._interceptor.original.write(self.loading_text + "\n")
                break
            # Calculate how much extra space to clear after anim frame is shown.
            extra_space_clear: int = self.anim_clear_length - len(c)
            text = f"{self.loading_text} {c}" + " " * extra_space_clear
            # Write + Reset cursor
            self._interceptor.original.write(text)
            self._interceptor.flush()
            sleep(self.anim_speed)
            self._interceptor.original.write(self._terminal.move_left(len(text)))

    @override
    def start(self, text: str = "Please Wait") -> None:
        # Capture stdout
        sys.stdout = self._interceptor
        self._running = True
        self.loading_text = text
        self.thread = Thread(target=self._animate)
        self.thread.daemon = True
        self.thread.start()

    @override
    def stop(self) -> None:
        # Release stdout
        sys.stdout = self._interceptor.original
        self._running = False
        # Block until end.
        if self.thread:
            self.thread.join()


if __name__ == "__main__":
    LoadingWidget(animation=loading_widget_anim_2).start()
    while True:
        pass
