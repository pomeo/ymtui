"""Left sidebar: Library categories + a Collection panel.

Library is the top navigation (categories). Picking a category either loads
tracks straight into Songs (Liked, Chart) or fills the bottom Collection panel
with a list of playlists/albums to drill into.
"""
from __future__ import annotations

from textual.message import Message
from textual.widgets import Label, ListItem, ListView

from ymtui.i18n import t


class Library(ListView):
    """Top navigation: fixed categories."""

    class CategorySelected(Message):
        def __init__(self, category: str) -> None:
            self.category = category
            super().__init__()

    # category key -> icon.  Liked/Chart/History/Wave load Songs directly; the
    # rest open a collection in the bottom panel. Labels come from i18n.
    CATEGORIES: list[tuple[str, str]] = [
        ('wave', '≈'),
        ('liked', '♥'),
        ('chart', '♫'),
        ('history', '↺'),
        ('daily', '★'),
        ('new-playlists', '✦'),
        ('new-releases', '◆'),
        ('my-playlists', '♪'),
        ('genres', '◇'),
        ('moods', '◇'),
        ('activities', '◇'),
        ('eras', '◇'),
    ]
    COLLECTION_CATEGORIES = {
        'daily', 'new-playlists', 'new-releases', 'my-playlists',
        'genres', 'moods', 'activities', 'eras',
    }
    _ICONS = dict(CATEGORIES)

    def __init__(self, **kwargs) -> None:
        items = [
            ListItem(Label(f'{icon}  {t("cat." + key)}'), id=key)
            for key, icon in self.CATEGORIES
        ]
        super().__init__(*items, **kwargs)
        self.border_title = t('panel.library')

    def retranslate(self) -> None:
        self.border_title = t('panel.library')
        for item in self.children:
            if item.id:
                item.query_one(Label).update(
                    f'{self._ICONS.get(item.id, "")}  {t("cat." + item.id)}'
                )

    @classmethod
    def index_of(cls, category: str) -> int | None:
        for i, (key, _) in enumerate(cls.CATEGORIES):
            if key == category:
                return i
        return None

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        event.stop()
        if event.item.id:
            self.post_message(self.CategorySelected(event.item.id))


class Collection(ListView):
    """Bottom panel: items (playlists or albums) of the active category."""

    class ItemSelected(Message):
        def __init__(self, source: dict) -> None:
            self.source = source
            super().__init__()

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.border_title = t('coll.my-playlists')
        self._items: list[dict] = []
        self._gen = 0

    @property
    def items(self) -> list[dict]:
        return self._items

    def load_items(self, title: str, items: list[dict]) -> None:
        self.loading = False
        self._items = items
        self.border_title = title
        # clear() is async; use a per-load generation so the freshly appended
        # ids never collide with the items still being removed.
        self.clear()
        self._gen += 1
        for i, item in enumerate(items):
            self.append(ListItem(Label(item.get('title', '—')), id=f'i{self._gen}_{i}'))

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        event.stop()
        iid = event.item.id or ''
        if '_' not in iid:
            return
        idx = int(iid.rsplit('_', 1)[1])
        if 0 <= idx < len(self._items):
            self.post_message(self.ItemSelected(self._items[idx]))
