"""Bottom 'Playing' panel: track info, status, and an overlaid progress bar."""
from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.message import Message
from textual.reactive import reactive
from textual.widgets import Label, Static

from ymtui.i18n import t

try:
    from textual_image.widget import Image as CoverImage
    COVER_AVAILABLE = True
except ImportError:  # optional extra: ymtui[cover]
    COVER_AVAILABLE = False

# Filled / empty styles for the progress bar (Yandex yellow on dark).
_FILLED = 'bold #1a1a1a on #ffdb4d'
_EMPTY = '#d0d0d0 on #2a2a2a'


def _fmt(seconds: float) -> str:
    seconds = int(max(0, seconds))
    return f'{seconds // 60}:{seconds % 60:02d}'


class ProgressLine(Static):
    """A single-line progress bar with the time string overlaid in the center."""

    class Clicked(Message):
        """Posted when the bar is clicked, carrying the 0..1 position fraction."""

        def __init__(self, fraction: float) -> None:
            self.fraction = fraction
            super().__init__()

    position: reactive[float] = reactive(0.0)
    duration: reactive[float] = reactive(0.0)

    def on_click(self, event) -> None:
        if self.duration <= 0:
            return
        width = max(self.size.width, 1)
        self.post_message(self.Clicked(min(1.0, max(0.0, event.x / width))))

    def watch_position(self, _: float) -> None:
        self.refresh()

    def watch_duration(self, _: float) -> None:
        self.refresh()

    def render(self) -> Text:
        width = max(self.size.width, 10)
        dur, pos = self.duration, self.position
        frac = min(1.0, pos / dur) if dur > 0 else 0.0
        filled = int(round(width * frac))

        if dur > 0:
            label = f'{_fmt(pos)}/{_fmt(dur)} (-{_fmt(dur - pos)})'
        else:
            label = '—'

        cells = [' '] * width
        start = max(0, (width - len(label)) // 2)
        for i, ch in enumerate(label):
            if start + i < width:
                cells[start + i] = ch

        text = Text()
        for i, ch in enumerate(cells):
            text.append(ch, style=_FILLED if i < filled else _EMPTY)
        return text


class NowPlaying(Container):
    """Bottom player panel matching the spotify-tui 'Playing' box."""

    track_title: reactive[str] = reactive('')
    track_artist: reactive[str] = reactive('')
    is_liked: reactive[bool] = reactive(False)
    is_playing: reactive[bool] = reactive(False)
    volume: reactive[int] = reactive(80)
    shuffle: reactive[bool] = reactive(False)
    repeat: reactive[bool] = reactive(False)
    device: reactive[str] = reactive('ymtui')

    def compose(self) -> ComposeResult:
        with Horizontal(id='np-body'):
            if COVER_AVAILABLE:
                yield CoverImage(id='np-cover')
            with Vertical(id='np-info'):
                yield Label(t('np.nothing'), id='np-title')
                yield Label('', id='np-artist')
                yield ProgressLine(id='np-progress')

    def on_mount(self) -> None:
        self._refresh_title_label()
        self._refresh_border()

    # ------------------------------------------------------------------
    # Album cover
    # ------------------------------------------------------------------

    def set_cover(self, image) -> None:
        """Set (or clear) the cover image (a PIL Image, or ``None``)."""
        if not COVER_AVAILABLE:
            return
        try:
            self.query_one('#np-cover', CoverImage).image = image
        except Exception:
            pass

    def show_cover(self, enabled: bool) -> None:
        self.set_class(enabled and COVER_AVAILABLE, 'with-cover')

    def retranslate(self) -> None:
        self._refresh_title_label()
        self._refresh_border()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_progress(self, position: float, duration: float) -> None:
        bar = self.query_one(ProgressLine)
        bar.position = position
        bar.duration = duration

    # ------------------------------------------------------------------
    # Watchers
    # ------------------------------------------------------------------

    def watch_track_title(self, _: str) -> None:
        self._refresh_title_label()

    def watch_is_liked(self, _: bool) -> None:
        self._refresh_title_label()

    def watch_is_playing(self, _: bool) -> None:
        self._refresh_title_label()

    def watch_track_artist(self, value: str) -> None:
        self.query_one('#np-artist', Label).update(value)

    def watch_volume(self, _: int) -> None:
        self._refresh_border()

    def watch_shuffle(self, _: bool) -> None:
        self._refresh_border()

    def watch_repeat(self, _: bool) -> None:
        self._refresh_border()

    def watch_device(self, _: str) -> None:
        self._refresh_border()

    # ------------------------------------------------------------------
    # Rendering helpers
    # ------------------------------------------------------------------

    def _refresh_title_label(self) -> None:
        glyph = '▶' if self.is_playing else '⏸'
        heart = '♥ ' if self.is_liked else ''
        title = self.track_title or t('np.nothing')
        try:
            self.query_one('#np-title', Label).update(f'{glyph}  {heart}{title}')
        except Exception:
            pass

    def _refresh_border(self) -> None:
        on, off = t('np.on'), t('np.off')
        shuffle = on if self.shuffle else off
        repeat = on if self.repeat else off
        self.border_title = (
            f'{t("np.playing")} ({self.device})  |  {t("np.shuffle")}: {shuffle}  |  '
            f'{t("np.repeat")}: {repeat}  |  {t("np.volume")}: {self.volume}%'
        )
