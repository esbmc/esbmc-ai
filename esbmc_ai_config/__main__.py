# Author: Yiannis Charalambous

from urwid import (
    MainLoop,
)

from esbmc_ai_config.context_manager import ContextManager
from esbmc_ai_config.contexts.main_menu import MainMenu


palette = [
    ("banner", "", "", "", "#ffa", "#60d"),
    ("streak", "", "", "", "g50", "#60a"),
    ("inside", "", "", "", "g38", "#808"),
    ("outside", "", "", "", "g27", "#a06"),
    ("bg", "", "", "", "g7", "#d06"),
]


def main() -> None:
    top_ctx = MainMenu()

    app: MainLoop = MainLoop(top_ctx.widget, palette=[("reversed", "standout", "")])
    ContextManager.init(app, top_ctx)
    app.run()


if __name__ == "__main__":
    main()
