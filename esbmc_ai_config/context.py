# Author: Yiannis Charalambous

import urwid


class Context(object):
    def __init__(self, widget: urwid.Widget) -> None:
        super().__init__()

        self.widget: urwid.Widget = widget
