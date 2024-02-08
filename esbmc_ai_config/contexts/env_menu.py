# Author: Yiannis Charalambous

import urwid

from esbmc_ai_config.models.env_config_loader import EnvConfigLoader
from esbmc_ai_config.contexts.base_menu import BaseMenu


class EnvMenu(BaseMenu):
    def __init__(self) -> None:
        self.config: EnvConfigLoader = EnvConfigLoader(create_missing_fields=True)
        choices: list = [field.name for field in self.config.fields]
        super().__init__(title="Setup Environment", choices=choices)

        top: urwid.Widget = urwid.Overlay(
            urwid.LineBox(self.widget),
            urwid.SolidFill("\N{MEDIUM SHADE}"),
            align="center",
            valign="middle",
            width=("relative", 60),
            height=("relative", 15),
            min_width=20,
            min_height=10,
        )

        self.widget = top
