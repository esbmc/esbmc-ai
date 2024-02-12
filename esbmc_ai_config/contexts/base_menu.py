# Author: Yiannis Charalambous

from typing_extensions import override
import urwid
from urwid import Button, Text, connect_signal, AttrMap

from esbmc_ai_config.context import Context
from esbmc_ai_config.widgets.back_button import BackButton


class BaseMenu(Context):
    def __init__(
        self,
        title: str,
        choices: list[str | urwid.Widget],
        back_choice: bool = True,
    ) -> None:
        """Creates a Menu context and displays it on the screen."""

        self.choices: list[str | urwid.Widget] = choices.copy()
        self.back_choice: bool = back_choice
        self.title: str = title

        super().__init__()

    def create_padding(self, menu: urwid.Widget) -> urwid.Padding:
        return urwid.Padding(
            menu,
            left=2,
            right=2,
        )

    @override
    def build_ui(self) -> urwid.Widget:
        choices: list[str | urwid.Widget] = self.choices.copy()
        if self.back_choice:
            choices.append(urwid.Divider())
            choices.append(BackButton())

        menu: urwid.ListBox = self.create_menu(title=self.title, choices=choices)
        return self.create_padding(menu)

    def item_chosen(self, button, choice) -> None:
        pass

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
