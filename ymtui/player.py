"""Audio player backed by libmpv (python-mpv)."""
from __future__ import annotations

from typing import Callable, Optional

try:
    import mpv
    _MPV_AVAILABLE = True
except ImportError:
    _MPV_AVAILABLE = False


class Player:
    """Audio-only streaming player.

    Requires ``python-mpv`` and a working libmpv installation.
    """

    def __init__(self) -> None:
        if not _MPV_AVAILABLE:
            raise RuntimeError(
                'python-mpv is not installed. Run: pip install python-mpv'
            )
        self._mpv = mpv.MPV(
            ytdl=False,
            video=False,
            terminal=False,
            input_terminal=False,
        )
        self._on_end: Optional[Callable[[], None]] = None
        self._current_url: Optional[str] = None

        @self._mpv.event_callback('end-file')
        def _on_end_file(event):
            # python-mpv passes an MpvEvent object; the end-file payload lives
            # in event.data.reason. EOF (0) == natural end — ignore stop/error.
            try:
                data = event.data
                reason = data.reason if data is not None else -1
            except Exception:
                reason = -1
            if reason == mpv.MpvEventEndFile.EOF and self._on_end:
                self._on_end()

    # ------------------------------------------------------------------
    # Playback control
    # ------------------------------------------------------------------

    def play(self, url: str, start: float = 0.0) -> None:
        self._current_url = url
        # mpv applies the `start` option when the file is loaded, so set it
        # before play(). 0 == from the beginning.
        self._mpv['start'] = str(max(0.0, float(start)))
        self._mpv.play(url)
        self._mpv.pause = False

    def toggle_pause(self) -> None:
        self._mpv.pause = not self._mpv.pause

    def stop(self) -> None:
        self._mpv.command('stop')
        self._current_url = None

    def seek_relative(self, delta: float) -> None:
        try:
            self._mpv.seek(delta, 'relative')
        except Exception:
            pass

    def seek_absolute(self, seconds: float) -> None:
        try:
            self._mpv.seek(max(0.0, seconds), 'absolute')
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def is_paused(self) -> bool:
        return bool(self._mpv.pause)

    @property
    def is_playing(self) -> bool:
        return self._current_url is not None and not self._mpv.idle_active

    @property
    def position(self) -> float:
        return float(self._mpv.time_pos or 0.0)

    @property
    def duration(self) -> float:
        return float(self._mpv.duration or 0.0)

    @property
    def volume(self) -> int:
        return int(self._mpv.volume or 100)

    @volume.setter
    def volume(self, value: int) -> None:
        self._mpv.volume = max(0, min(100, int(value)))

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    def on_track_end(self, callback: Callable[[], None]) -> None:
        """Register a callback invoked when a track ends naturally."""
        self._on_end = callback

    # ------------------------------------------------------------------

    def terminate(self) -> None:
        self._mpv.terminate()
