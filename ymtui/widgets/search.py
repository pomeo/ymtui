"""Top search input."""
from __future__ import annotations

from textual.message import Message
from textual.widgets import Input

from ymtui.i18n import t


class SearchBar(Input):
    """A search box that emits a Query message on submit."""

    class Query(Message):
        def __init__(self, query: str) -> None:
            self.query = query
            super().__init__()

    def __init__(self, **kwargs) -> None:
        super().__init__(placeholder=t('search.placeholder'), **kwargs)
        self.border_title = t('panel.search')

    def retranslate(self) -> None:
        self.placeholder = t('search.placeholder')
        self.border_title = t('panel.search')

    def on_input_submitted(self, event: Input.Submitted) -> None:
        event.stop()
        query = self.value.strip()
        if query:
            self.post_message(self.Query(query))
