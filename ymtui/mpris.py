"""MPRIS2 D-Bus interface.

Позволяет:
  - управлять плеером через мультимедиа-клавиши (play/pause, next, prev)
  - получать "now playing" во внешних программах (playerctl, waybar, conky…)

Зависимость: mpris-server (pip install mpris-server)
Системная зависимость: python3-gi (GLib main loop)

Проверка:
    playerctl -p ymtui metadata --format '{{status}} {{artist}} – {{title}}'

AwesomeWM — rc.lua, привязка мультимедиа-клавиш:
    awful.key({}, "XF86AudioPlay",  function() awful.spawn("playerctl play-pause") end),
    awful.key({}, "XF86AudioNext",  function() awful.spawn("playerctl next")       end),
    awful.key({}, "XF86AudioPrev",  function() awful.spawn("playerctl previous")   end),
"""
from __future__ import annotations

import os
import re
import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from yandex_music import Track
    from ymtui.app import YMPlayerApp

try:
    from mpris_server import (
        MetadataObj,
        MprisAdapter,
        PlayerEventAdapter,
        PlayState,
        Server,
    )
    _AVAILABLE = True
except ImportError:
    _AVAILABLE = False


def _track_id_path(track: 'Track') -> str:
    """Build a valid D-Bus object path from a Yandex track id."""
    raw = str(getattr(track, 'id', '') or '0')
    safe = re.sub(r'[^A-Za-z0-9_]', '_', raw)
    return f'/com/yandex/music/track/{safe}'


if _AVAILABLE:
    class _YMAdapter(MprisAdapter):
        def __init__(self, app: 'YMPlayerApp') -> None:
            self._app = app
            self._track: 'Track | None' = None

        # ------------------------------------------------------------------
        # Metadata  (must use proper mpris keys — MetadataObj handles that)
        # ------------------------------------------------------------------

        def metadata(self) -> MetadataObj:
            t = self._track
            if not t:
                return MetadataObj(title='Nothing playing')
            artists = [a.name for a in t.artists if a.name] if t.artists else []
            album = t.albums[0].title if t.albums else None
            length = int(t.duration_ms) * 1000 if t.duration_ms else None  # μs
            return MetadataObj(
                track_id=_track_id_path(t),
                title=t.title or '',
                artists=artists,
                album=album,
                length=length,
            )

        def get_stream_title(self) -> str:
            t = self._track
            if not t:
                return ''
            artists = ', '.join(a.name for a in t.artists if a.name) if t.artists else ''
            return f'{artists} — {t.title}' if artists else (t.title or '')

        # ------------------------------------------------------------------
        # State
        # ------------------------------------------------------------------

        def get_playstate(self) -> PlayState:
            if self._app.player.is_paused:
                return PlayState.PAUSED
            if self._app.player.is_playing:
                return PlayState.PLAYING
            return PlayState.STOPPED

        def get_volume(self) -> float:
            return self._app.player.volume / 100.0

        def get_current_position(self) -> int:
            return int(self._app.player.position * 1_000_000)  # microseconds

        def get_shuffle(self) -> bool:
            return self._app.shuffle

        def is_repeating(self) -> bool:
            return self._app.repeat

        def is_playlist(self) -> bool:
            return True

        def get_rate(self) -> float:
            return 1.0

        def get_minimum_rate(self) -> float:
            return 1.0

        def get_maximum_rate(self) -> float:
            return 1.0

        def can_go_next(self) -> bool:
            return True

        def can_go_previous(self) -> bool:
            return True

        def can_play(self) -> bool:
            return True

        def can_pause(self) -> bool:
            return True

        def can_seek(self) -> bool:
            return False

        def can_control(self) -> bool:
            return True

        # ------------------------------------------------------------------
        # Commands (called from the D-Bus / GLib thread → marshal to the app)
        # ------------------------------------------------------------------

        def next(self) -> None:
            self._app.call_from_thread(self._app.next_track)

        def previous(self) -> None:
            self._app.call_from_thread(self._app.previous_track)

        def play(self) -> None:
            self._app.call_from_thread(self._app.resume_playback)

        def resume(self) -> None:
            self._app.call_from_thread(self._app.resume_playback)

        def pause(self) -> None:
            self._app.call_from_thread(self._app.pause_playback)

        def stop(self) -> None:
            self._app.call_from_thread(self._app.player.stop)

        def set_volume(self, volume: float) -> None:
            self._app.player.volume = int(volume * 100)


class MprisServer:
    """Тонкая обёртка над Server: запускает GLib loop в фоновом треде."""

    def __init__(self, app: 'YMPlayerApp') -> None:
        self._server: 'Server | None' = None
        self._adapter: '_YMAdapter | None' = None
        self._events: 'PlayerEventAdapter | None' = None
        if not _AVAILABLE:
            return
        self._adapter = _YMAdapter(app)
        self._server = Server('ymtui', adapter=self._adapter)

    def start(self) -> None:
        if self._server is None:
            return
        if not self._publish_safely():
            # Couldn't get on the bus at all (no session bus, etc.) — run
            # without MPRIS rather than crashing.
            self._server = None
            self._adapter = None
            return
        # Event adapter lets us push live property changes to D-Bus listeners.
        self._events = PlayerEventAdapter(
            root=self._server.root, player=self._server.player
        )
        self._server.set_event_adapter(self._events)
        thread = threading.Thread(target=self._server.loop, daemon=True)
        thread.start()

    def _publish_safely(self) -> bool:
        """Publish to D-Bus, tolerating a second running copy.

        The first copy owns ``org.mpris.MediaPlayer2.ymtui`` (so
        ``playerctl -p ymtui`` keeps working). A second copy falls back to a
        unique ``…ymtui.instance<PID>`` name instead of crashing.
        """
        try:
            self._server.publish()
            return True
        except Exception:
            pass
        try:
            self._server.dbus_name = f'ymtui.instance{os.getpid()}'
            self._server.publish()
            return True
        except Exception:
            return False

    def update(self, track: 'Track') -> None:
        """Сообщить MPRIS о смене трека."""
        if self._adapter is None:
            return
        self._adapter._track = track
        self._emit('on_title')
        self._emit('on_playback')

    def update_playstate(self) -> None:
        """Сообщить MPRIS об изменении состояния (пауза/воспроизведение)."""
        self._emit('on_playback')

    def _emit(self, method: str) -> None:
        if self._events is None:
            return
        try:
            getattr(self._events, method)()
        except Exception:
            pass
