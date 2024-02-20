# Author: Yiannis Charalambous

from typing_extensions import override

import urwid
from esbmc_ai_config.context_manager import ContextManager
from esbmc_ai_config.contexts.base_menu import BaseMenu
from esbmc_ai_config.contexts.esbmc_menu.esbmc_manage import ESBMCManage
from esbmc_ai_config.widgets.text_input_button import TextInputButton
from esbmc_ai_config.models.config_manager import ConfigManager


class AIConfigMenu(BaseMenu):
    def __init__(self) -> None:
        super().__init__(title="AI Configuration", choices=self._get_menu_choices())

    def _get_menu_choices(self) -> list[str | urwid.Widget]:
        return [
            "AI Model",
            "Temperature",
            "API Request Cooldown",
        ]

    @override
    def build_ui(self) -> urwid.Widget:
        self.choices = self._get_menu_choices()
        menu: urwid.Widget = super().build_ui()
        overlay: urwid.Widget = urwid.Overlay(
            urwid.LineBox(menu),
            urwid.SolidFill("\N{MEDIUM SHADE}"),
            align="center",
            valign="middle",
            width=("relative", 60),
            height=("relative", 15),
            min_width=20,
            min_height=10,
        )
        return overlay
