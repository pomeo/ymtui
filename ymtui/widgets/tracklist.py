"""Songs table with liked/playing indicators."""
from __future__ import annotations

from textual.message import Message
from textual.widgets import DataTable
from yandex_music import Track

from ymtui.i18n import t


def _fmt_duration(ms: int | None) -> str:
    if not ms:
        return '—'
    s = ms // 1000
    return f'{s // 60}:{s % 60:02d}'


def _fmt_artists(track: Track) -> str:
    if track.artists:
        return ', '.join(a.name for a in track.artists if a.name)
    return '—'


def _album(track: Track) -> str:
    return track.albums[0].title if track.albums else '—'


class TrackList(DataTable):
    """Displays a list of tracks; row 0 column shows ♥ / ▶ indicators."""

    class TrackSelected(Message):
        def __init__(self, track: Track, index: int) -> None:
            self.track = track
            self.index = index
            super().__init__()

    def __init__(self, **kwargs) -> None:
        super().__init__(cursor_type='row', zebra_stripes=True, **kwargs)
        self.border_title = t('panel.songs')
        self._tracks: list[Track] = []
        self._liked: list[bool] = []
        self._playing_index: int = -1
        self._ind_col = None
        self._title: str = ''

    def on_mount(self) -> None:
        self._add_columns()

    def _add_columns(self) -> None:
        self._ind_col = self.add_column('', width=3)
        self.add_column(t('col.title'), width=24)
        self.add_column(t('col.artist'), width=17)
        self.add_column(t('col.album'), width=14)
        self.add_column(t('col.time'), width=5)

    def retitle(self, title: str) -> None:
        self._title = title
        self.border_title = f'{t("panel.songs")} · {title}' if title else t('panel.songs')

    def retranslate(self) -> None:
        """Rebuild column headers (and re-render rows) in the current language."""
        tracks, liked, playing = self._tracks, self._liked, self._playing_index
        self.clear(columns=True)
        self._add_columns()
        self._tracks, self._liked, self._playing_index = tracks, liked, playing
        for i, track in enumerate(tracks):
            album = track.albums[0].title if track.albums else '—'
            self.add_row(
                self._indicator(i), track.title or '—', _fmt_artists(track),
                album, _fmt_duration(track.duration_ms), key=str(i),
            )

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def load_tracks(
        self,
        tracks: list[Track],
        title: str = 'Songs',
        liked_ids: set[str] | None = None,
    ) -> None:
        liked_ids = liked_ids or set()
        self.loading = False
        # Copy so appending (e.g. «Моя волна» extension) never mutates the
        # caller's list; the playback queue aliases this copy on purpose.
        self._tracks = list(tracks)
        self._liked = [str(t.id) in liked_ids for t in tracks]
        self._playing_index = -1
        self.retitle(title)
        self.clear()
        for i, track in enumerate(tracks):
            self.add_row(
                self._indicator(i),
                track.title or '—',
                _fmt_artists(track),
                _album(track),
                _fmt_duration(track.duration_ms),
                key=str(i),
            )

    def append_tracks(self, tracks: list[Track], liked_ids: set[str] | None = None) -> None:
        """Append more tracks (used by «Моя волна» to extend the queue)."""
        liked_ids = liked_ids or set()
        start = len(self._tracks)
        for j, track in enumerate(tracks):
            i = start + j
            self._tracks.append(track)
            self._liked.append(str(track.id) in liked_ids)
            album = track.albums[0].title if track.albums else '—'
            self.add_row(
                self._indicator(i),
                track.title or '—',
                _fmt_artists(track),
                album,
                _fmt_duration(track.duration_ms),
                key=str(i),
            )

    def _indicator(self, i: int) -> str:
        heart = '♥' if (i < len(self._liked) and self._liked[i]) else ' '
        play = '▶' if i == self._playing_index else ' '
        return f'{heart} {play}'

    def set_playing(self, index: int) -> None:
        """Mark a row as currently playing (moves the ▶ indicator)."""
        old = self._playing_index
        self._playing_index = index
        for i in (old, index):
            if 0 <= i < len(self._tracks):
                try:
                    self.update_cell(str(i), self._ind_col, self._indicator(i))
                except Exception:
                    pass

    def set_liked(self, index: int, liked: bool) -> None:
        if 0 <= index < len(self._liked):
            self._liked[index] = liked
            try:
                self.update_cell(str(index), self._ind_col, self._indicator(index))
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Selection
    # ------------------------------------------------------------------

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        event.stop()
        idx = int(event.row_key.value)
        if 0 <= idx < len(self._tracks):
            self.post_message(self.TrackSelected(self._tracks[idx], idx))

    @property
    def tracks(self) -> list[Track]:
        return self._tracks

    @property
    def cursor_index(self) -> int:
        return self.cursor_row
