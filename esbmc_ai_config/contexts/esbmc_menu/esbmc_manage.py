# Author: Yiannis Charalambous

from typing_extensions import override
import requests
from requests.status_codes import codes as status_codes

import urwid

from esbmc_ai_config.models import ConfigManager
from esbmc_ai_config.context import Context
from esbmc_ai_config.widgets.back_button import BackButton


class ESBMCManage(Context):
    license_url: str = "https://raw.githubusercontent.com/esbmc/esbmc/master/COPYING"

    def __init__(self) -> None:
        response: requests.Response = requests.get(ESBMCManage.license_url)
        if response.status_code == status_codes.ok:
            self.license: str = response.text
        else:
            self.license: str = (
                f"Couldn't get the license: status code: {response.status_code}"
            )

        super().__init__(self.build_ui())

    @property
    def license_accepted(self) -> bool:
        return bool(ConfigManager.env_config.values["ESBMC_LICENSE_AGREEMENT"])

    @license_accepted.setter
    def license_accepted(self, value: bool) -> None:
        ConfigManager.env_config.values["ESBMC_LICENSE_AGREEMENT"] = value

    def _on_accept_license(self, button) -> None:
        self.license_accepted = True
        self.frame.set_body(self._build_ui())

    def _build_ui_license_agreement(self) -> urwid.Widget:
        body: list[urwid.Widget] = [
            urwid.Divider(),
            urwid.Text("Read and accept the license agreement of ESBMC"),
            urwid.Divider(),
            urwid.Text(self.license),
            urwid.Columns(
                [
                    BackButton(),
                    urwid.AttrMap(
                        urwid.Button(
                            "Accept License",
                            on_press=self._on_accept_license,
                        ),
                        None,
                        focus_map="reversed",
                    ),
                ]
            ),
        ]

        return urwid.ScrollBar(urwid.ListBox(urwid.SimpleFocusListWalker(body)))

    def _build_ui(self) -> urwid.Widget:
        body: list[urwid.Widget] = [
            urwid.Divider(),
            BackButton(),
        ]

        return urwid.ScrollBar(urwid.ListBox(urwid.SimpleFocusListWalker(body)))

    @override
    def build_ui(self) -> urwid.Widget:
        content: urwid.Widget
        if self.license_accepted:
            content = self._build_ui()
        else:
            content = self._build_ui_license_agreement()

        self.frame: urwid.Frame = urwid.Frame(
            header=urwid.Text("Manage ESBMC Installations"),
            footer=urwid.Text("www.esbmc.org"),
            body=content,
            focus_part="body",
        )

        return self.frame
