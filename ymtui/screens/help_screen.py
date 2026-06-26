"""Modal help overlay listing key bindings."""
from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Center, Middle
from textual.screen import ModalScreen
from textual.widgets import Static

from ymtui.i18n import t


class HelpScreen(ModalScreen):
    BINDINGS = [
        Binding('escape', 'dismiss', 'Close'),
        Binding('question_mark', 'dismiss', 'Close'),
        Binding('q', 'dismiss', 'Close'),
    ]

    def compose(self) -> ComposeResult:
        with Center():
            with Middle():
                box = Static(t('help.body'), id='help-box')
                box.border_title = t('help.title')
                yield box
