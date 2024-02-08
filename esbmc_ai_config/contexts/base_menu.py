# Author: Yiannis Charalambous

import urwid
from urwid import Button, Text, connect_signal, AttrMap

from esbmc_ai_config.context import Context
from esbmc_ai_config.context_manager import ContextManager


class BaseMenu(Context):
    def __init__(
        self,
        title: str,
        choices: list[str | urwid.Widget],
        back_choice: bool = True,
    ) -> None:
        """Creates a Menu context and displays it on the screen."""

        _choices: list[str | urwid.Widget] = choices.copy()
        if back_choice:
            _choices.append(urwid.Divider())
            _choices.append("Back")

        menu: urwid.ListBox = self.create_menu(title=title, choices=_choices)

        menu_box: urwid.WidgetDecoration = urwid.Padding(
            menu,
            left=2,
            right=2,
        )

        super().__init__(menu_box)

    def item_chosen(self, button, choice) -> None:
        if choice == "Back":
            ContextManager.pop_context()

    def create_menu(self, title, choices: list[str | urwid.Widget]) -> urwid.ListBox:
        body: list[urwid.Widget] = [Text(title), urwid.Divider()]
        for c in choices:
            if isinstance(c, str):
                button = Button(c)
                connect_signal(
                    obj=button,
                    name="click",
                    callback=self.item_chosen,
                    user_arg=c,
                )
                # Reverse attributes when focused
                body.append(AttrMap(button, None, focus_map="reversed"))
            elif isinstance(c, urwid.Widget):
                body.append(c)
            else:
                raise ValueError(f"create_menu: {c} is not a str or urwid.Widget")

        return urwid.ListBox(urwid.SimpleFocusListWalker(body))
