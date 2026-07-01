"""Main Textual application."""
from __future__ import annotations

import dataclasses
import io
import random
import uuid

from textual.app import App, SystemCommand
from textual.theme import Theme
from yandex_music import Track

from ymtui import i18n
from ymtui.api.client import YMClient
from ymtui.config import get_token
from ymtui.mpris import MprisServer
from ymtui.player import Player
from ymtui.screens.main_screen import MainScreen
from ymtui.state import load_state, save_state
from ymtui.widgets.now_playing import COVER_AVAILABLE, NowPlaying
from ymtui.widgets.tracklist import TrackList

# Yandex-Music-flavoured theme (yellow accent on dark).
YANDEX_THEME = Theme(
    name='yandex',
    primary='#ffdb4d',
    secondary='#ffcc00',
    accent='#ffdb4d',
    foreground='#e8e8e8',
    background='#161616',
    surface='#1e1e1e',
    panel='#242424',
    success='#7ec699',
    warning='#ffcc00',
    error='#e06c75',
    dark=True,
    variables={
        'border': '#3a3a3a',
        # Highlighted list/table item — focused list: black on yellow…
        'block-cursor-foreground': '#161616',
        'block-cursor-background': '#ffdb4d',
        'block-cursor-text-style': 'bold',
        # …blurred (unfocused) list: light text on a faint yellow tint
        'block-cursor-blurred-foreground': '#e8e8e8',
        'block-cursor-blurred-background': '#ffdb4d 20%',
        'block-cursor-blurred-text-style': 'none',
        'input-selection-background': '#ffdb4d 35%',
    },
)


class YMPlayerApp(App):
    TITLE = 'Yandex Music'
    CSS_PATH = 'styles/app.tcss'

    def __init__(self, token: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self._client = YMClient(token)
        self.player = Player()
        self._queue: list[Track] = []
        self._current_index: int = -1
        self._current_track: Track | None = None
        self.shuffle: bool = False
        self.repeat_mode: str = 'off'  # 'off' | 'all' | 'one'
        self.player.on_track_end(self._on_track_end)
        self._mpris = MprisServer(self)
        # Persisted session state (last source / track / position)
        self.state: dict = load_state()
        i18n.set_language(self.state.get('language', 'en'))
        self._started: bool = False          # has mpv played anything this run?
        self._resume_position: float = 0.0   # seek offset for the primed track
        self._save_counter: int = 0
        # «Моя волна» state
        self._wave: bool = False
        self._wave_batches: dict[str, str] = {}  # track id -> batch id (for feedback)
        self._wave_fetching: bool = False
        self._wave_last_batch_ids: set[str] = set()  # ids of the previous batch
        # Album cover (optional, off by default)
        self._cover_enabled: bool = bool(self.state.get('cover', False))
        self._cover_cache: dict[str, bytes] = {}  # album id -> image bytes
        # Play reporting (отстукивание прослушиваний)
        self._play_id: str | None = None
        self._play_from: str = 'web-playlist-playlist-default'
        self._play_context: str | None = None
        self._play_context_item: str | None = None
        self._play_playlist_id: str | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def on_mount(self) -> None:
        self.register_theme(YANDEX_THEME)
        # Restore the saved theme (falls back to 'yandex' if missing/unknown).
        saved = self.state.get('theme')
        self.theme = saved if saved in self.available_themes else 'yandex'
        # Persist any later theme change (e.g. via the command palette).
        self.watch(self, 'theme', self._persist_theme, init=False)
        self._apply_palette_label()
        self.push_screen(MainScreen(self._client))
        self._mpris.start()
        self.set_interval(1.0, self._tick_progress)

    def _apply_palette_label(self) -> None:
        """Translate Textual's built-in 'palette' footer hint (Ctrl+P)."""
        key = self.COMMAND_PALETTE_BINDING
        bindings = self._bindings.key_to_bindings.get(key)
        if not bindings:
            return
        self._bindings.key_to_bindings[key] = [
            dataclasses.replace(b, description=i18n.t('bind.palette'))
            if b.action and 'command_palette' in b.action else b
            for b in bindings
        ]

    def _persist_theme(self, theme_name: str) -> None:
        self.state['theme'] = theme_name
        save_state(self.state)

    # ------------------------------------------------------------------
    # Language
    # ------------------------------------------------------------------

    def get_system_commands(self, screen):
        yield from super().get_system_commands(screen)
        for lang in i18n.available_languages():
            name = i18n.LANGUAGE_NAMES.get(lang, lang)
            yield SystemCommand(
                i18n.t('cmd.language', name=name),
                i18n.t('cmd.language.help'),
                (lambda lang=lang: self.set_language(lang)),
            )
        # Album cover toggle (label shows the state it will switch to).
        target = i18n.t('np.off') if self._cover_enabled else i18n.t('np.on')
        yield SystemCommand(
            i18n.t('cmd.cover', state=target),
            i18n.t('cmd.cover.help'),
            (lambda: self.set_cover_enabled(not self._cover_enabled)),
        )

    # ------------------------------------------------------------------
    # Album cover
    # ------------------------------------------------------------------

    @property
    def cover_enabled(self) -> bool:
        return self._cover_enabled and COVER_AVAILABLE

    def set_cover_enabled(self, enabled: bool) -> None:
        if enabled and not COVER_AVAILABLE:
            self.notify(i18n.t('cover.missing'), severity='warning')
            return
        self._cover_enabled = enabled
        self.state['cover'] = enabled
        save_state(self.state)
        try:
            np = self.screen.query_one(NowPlaying)
            np.show_cover(enabled)
            if enabled and self._current_track is not None:
                self._fetch_cover(self._current_track)
            elif not enabled:
                np.set_cover(None)
        except Exception:
            pass

    def _fetch_cover(self, track: Track) -> None:
        if not self.cover_enabled or track is None:
            return
        album_id = str(track.albums[0].id) if track.albums else None
        self.run_worker(lambda: self._load_cover(track, album_id), thread=True)

    def _load_cover(self, track: Track, album_id: str | None) -> None:
        data = self._cover_cache.get(album_id) if album_id else None
        if data is None:
            data = self._client.cover_bytes(track)
            if data and album_id:
                self._cover_cache[album_id] = data
        if not data:
            return
        # textual-image needs a PIL Image (raw bytes are treated as a path).
        try:
            from PIL import Image as PILImage
            image = PILImage.open(io.BytesIO(data))
            image.load()
        except Exception:
            return
        self.call_from_thread(self._apply_cover, track, image)

    def _apply_cover(self, track: Track, image) -> None:
        # Apply only if this is still the current track.
        cur = self._current_track
        if cur is not None and str(cur.id) == str(track.id):
            try:
                self.screen.query_one(NowPlaying).set_cover(image)
            except Exception:
                pass

    def set_language(self, lang: str) -> None:
        if lang not in i18n.available_languages():
            return
        i18n.set_language(lang)
        self.state['language'] = lang
        save_state(self.state)
        self._apply_palette_label()
        try:
            self.screen.retranslate()
        except Exception:
            pass

    def on_unmount(self) -> None:
        self._persist_position()
        self.player.terminate()

    # ------------------------------------------------------------------
    # Progress ticker
    # ------------------------------------------------------------------

    def _tick_progress(self) -> None:
        # Before the first play, keep the primed/idle display (e.g. a restored
        # track shown at its saved position) instead of resetting it to 0:00.
        if not self._started:
            return
        try:
            self.screen.query_one(NowPlaying).set_progress(
                self.player.position, self.player.duration
            )
        except Exception:
            pass
        # Persist position periodically so a crash loses little.
        if not self.player.is_paused:
            self._save_counter += 1
            if self._save_counter >= 10:
                self._save_counter = 0
                self._persist_position()

    # ------------------------------------------------------------------
    # Play reporting (отстукивание прослушиваний — только на финише трека)
    # ------------------------------------------------------------------

    def set_play_context(self, from_: str, context: str | None,
                         context_item: str | None, playlist_id: str | None) -> None:
        self._play_from = from_
        self._play_context = context
        self._play_context_item = context_item
        self._play_playlist_id = playlist_id

    def _report_skip(self) -> None:
        """Report the current track as skipped (next / previous / new selection)."""
        self._report_play(self.player.position, change_reason='skip')

    def _report_play(self, played: float, change_reason: str | None = None) -> None:
        track = self._current_track
        if track is None or not self._started:
            return
        length = (track.duration_ms or 0) / 1000
        pid, frm, plid = self._play_id, self._play_from, self._play_playlist_id
        ctx, item = self._play_context, self._play_context_item
        # Radio plays need the batch id of the track's «Моя волна» batch.
        batch = self._wave_batches.get(str(track.id)) if self._wave else None
        self.run_worker(
            lambda: self._client.report_play(
                track, frm, played, length, playlist_id=plid, play_id=pid,
                change_reason=change_reason, context=ctx, context_item=item,
                batch_id=batch,
            ),
            thread=True,
        )

    # ------------------------------------------------------------------
    # Playback
    # ------------------------------------------------------------------

    def play_track(self, track: Track, queue_index: int) -> None:
        """Start playing a track and update the queue position."""
        self._report_skip()  # leaving the current track (if any)
        self._queue = self.screen.query_one(TrackList).tracks
        self._current_index = queue_index
        self._start_track(track)

    def toggle_play(self) -> None:
        # First play after a restore: start the primed track at its saved offset.
        if not self._started and self._current_track is not None:
            seek = self._resume_position
            self._resume_position = 0.0
            self._start_track(self._current_track, seek=seek)
            return
        self.player.toggle_pause()
        self._sync_playstate()
        self._persist_position()

    def resume_playback(self) -> None:
        if self.player.is_paused:
            self.player.toggle_pause()
            self._sync_playstate()

    def pause_playback(self) -> None:
        if not self.player.is_paused:
            self.player.toggle_pause()
            self._sync_playstate()

    def _sync_playstate(self) -> None:
        try:
            self.screen.query_one(NowPlaying).is_playing = not self.player.is_paused
        except Exception:
            pass
        self._mpris.update_playstate()

    def next_track(self, skipped: bool = True) -> None:
        if not self._queue:
            return
        if skipped:
            self._report_skip()  # outgoing track skipped
        if self._wave:
            # «Моя волна»: sequential, infinite — keep the queue topped up.
            if skipped:
                self._wave_feedback_skip()
            if self._current_index < len(self._queue) - 1:
                self._current_index += 1
                self._start_track(self._queue[self._current_index])
            self._extend_wave_if_needed()
            return
        if self.shuffle:
            self._current_index = random.randrange(len(self._queue))
        elif self._current_index < len(self._queue) - 1:
            self._current_index += 1
        elif self.repeat_mode == 'all':
            self._current_index = 0  # wrap to the start of the queue
        else:
            return
        self._start_track(self._queue[self._current_index])

    def previous_track(self) -> None:
        if self._queue and self._current_index > 0:
            self._report_skip()  # leaving the current track
            self._current_index -= 1
            self._start_track(self._queue[self._current_index])

    def toggle_shuffle(self) -> None:
        self.shuffle = not self.shuffle
        self._safe_np(lambda np: setattr(np, 'shuffle', self.shuffle))

    def toggle_repeat(self) -> None:
        # Cycle: off → all → one → off
        self.repeat_mode = {'off': 'all', 'all': 'one', 'one': 'off'}[self.repeat_mode]
        self._safe_np(lambda np: setattr(np, 'repeat', self.repeat_mode))

    def seek(self, delta: float) -> None:
        """Seek the playing track by ``delta`` seconds (or scrub a primed one)."""
        if self._started:
            self.player.seek_relative(delta)
            self._optimistic_progress(self.player.position + delta)
            self._persist_position()
        elif self._current_track is not None:
            dur = (self._current_track.duration_ms or 0) / 1000
            self._resume_position = min(dur, max(0.0, self._resume_position + delta))
            self._optimistic_progress(self._resume_position)

    def seek_fraction(self, fraction: float) -> None:
        """Seek to a fraction (0..1) of the track — used by progress-bar clicks."""
        fraction = min(1.0, max(0.0, fraction))
        if self._started:
            duration = self.player.duration
            if duration > 0:
                self.player.seek_absolute(fraction * duration)
                self._optimistic_progress(fraction * duration)
                self._persist_position()
        elif self._current_track is not None:
            dur = (self._current_track.duration_ms or 0) / 1000
            seek = fraction * dur
            self._resume_position = 0.0
            self._start_track(self._current_track, seek=seek)

    def _optimistic_progress(self, position: float) -> None:
        """Update the progress bar immediately instead of waiting for the tick."""
        try:
            np = self.screen.query_one(NowPlaying)
            duration = self.player.duration if self._started else \
                (self._current_track.duration_ms or 0) / 1000 if self._current_track else 0
            np.set_progress(max(0.0, position), duration)
        except Exception:
            pass

    def change_volume(self, delta: int) -> None:
        self.player.volume = max(0, min(100, self.player.volume + delta))
        self._safe_np(lambda np: setattr(np, 'volume', self.player.volume))

    def toggle_like_current(self) -> None:
        if not self._current_track:
            return
        liked = self._client.toggle_like(self._current_track)
        self._safe_np(lambda np: setattr(np, 'is_liked', liked))
        try:
            self.screen.query_one(TrackList).set_liked(self._current_index, liked)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Internal playback helpers
    # ------------------------------------------------------------------

    def _start_track(self, track: Track, seek: float = 0.0) -> None:
        self._current_track = track
        self._started = True
        self.run_worker(lambda: self._stream_track(track, seek), thread=True)

    def _stream_track(self, track: Track, seek: float = 0.0) -> None:
        url = self._client.get_stream_url(track)
        if url:
            self.call_from_thread(self._play_url, track, url, seek)

    def _play_url(self, track: Track, url: str, seek: float = 0.0) -> None:
        self.player.play(url, start=seek)
        artists = ', '.join(a.name for a in track.artists) if track.artists else ''
        try:
            np = self.screen.query_one(NowPlaying)
            np.track_title = track.title or ''
            np.track_artist = artists
            np.is_playing = True
            np.is_liked = self._client.is_liked(track)
            np.volume = self.player.volume
        except Exception:
            pass
        try:
            self.screen.query_one(TrackList).set_playing(self._current_index)
        except Exception:
            pass
        self._mpris.update(track)
        self._persist_track()
        self._fetch_cover(track)
        # New play: fresh play_id (used by the finish report when this track ends).
        self._play_id = str(uuid.uuid4())
        self._save_counter = 0
        if self._wave and track.id:
            tid = str(track.id)
            batch = self._wave_batches.get(tid)
            self.run_worker(lambda: self._client.wave_track_started(tid, batch), thread=True)

    # ------------------------------------------------------------------
    # «Моя волна» helpers
    # ------------------------------------------------------------------

    def start_wave(self, batch_id: str | None, tracks: list[Track]) -> None:
        self._wave = True
        self._wave_fetching = False
        self._wave_batches = {str(t.id): batch_id for t in tracks if t.id}
        self._wave_last_batch_ids = {str(t.id) for t in tracks if t.id}

    def exit_wave(self) -> None:
        self._wave = False
        self._wave_batches = {}
        self._wave_last_batch_ids = set()

    def _extend_wave_if_needed(self) -> None:
        if not self._wave or self._wave_fetching or not self._queue:
            return
        if self._current_index >= len(self._queue) - 2:
            last = self._queue[-1]
            last_id = str(last.id) if last.id else None
            self._wave_fetching = True
            self.run_worker(lambda: self._fetch_wave_more(last_id), thread=True)

    def _fetch_wave_more(self, last_id: str | None) -> None:
        tracks, batch_id = self._client.wave_batch(queue=last_id)
        self.call_from_thread(self._append_wave, tracks, batch_id)

    def _append_wave(self, tracks: list[Track], batch_id: str | None) -> None:
        self._wave_fetching = False
        if not tracks:
            return
        try:
            tl = self.screen.query_one(TrackList)
        except Exception:
            return
        # Drop only the overlap with the *previous* batch (usually the single
        # echoed continuation track). A radio may legitimately replay a track
        # later, so we don't dedup against the whole queue — that would shrink
        # batches and eventually starve the stream.
        prev, seen = self._wave_last_batch_ids, set()
        fresh: list[Track] = []
        for t in tracks:
            tid = str(t.id) if t.id else None
            if not tid or tid in prev or tid in seen:
                continue
            seen.add(tid)
            self._wave_batches[tid] = batch_id
            fresh.append(t)
        self._wave_last_batch_ids = {str(t.id) for t in tracks if t.id}
        if fresh:
            # The queue is the same list object as the table's tracks, so
            # appending rows also extends the playback queue.
            try:
                tl.append_tracks(fresh, self._client.liked_ids())
            except Exception:
                pass

    def _wave_feedback_skip(self) -> None:
        track = self._current_track
        if not track or not track.id:
            return
        tid = str(track.id)
        batch = self._wave_batches.get(tid)
        pos = self.player.position
        self.run_worker(lambda: self._client.wave_skip(tid, pos, batch), thread=True)

    # ------------------------------------------------------------------
    # State persistence
    # ------------------------------------------------------------------

    def save_source(self, source: dict) -> None:
        """Remember the currently open Songs source (playlist/album/section)."""
        self.state['source'] = source
        save_state(self.state)

    def save_category(self, category: str) -> None:
        """Remember the active Library category (for restoring the sidebar)."""
        self.state['category'] = category
        save_state(self.state)

    def save_tag(self, tag: dict | None) -> None:
        """Remember (or clear) the metatag drilled into, for restoring."""
        if tag:
            self.state['tag'] = tag
        else:
            self.state.pop('tag', None)
        save_state(self.state)

    def _persist_track(self) -> None:
        if self._current_track is None:
            return
        self.state['track_id'] = str(self._current_track.id)
        self.state['queue_index'] = self._current_index
        self.state['position'] = self.player.position
        save_state(self.state)

    def _persist_position(self) -> None:
        # Only overwrite the saved position once we've actually played this run,
        # otherwise a launch-then-quit would clobber the resume point with 0.
        if not self._started:
            return
        self.state['position'] = self.player.position
        save_state(self.state)

    def prime_resume(self, track: Track, index: int, position: float,
                     queue: list[Track]) -> None:
        """Load a restored track into the UI (paused) ready to resume on play."""
        self._queue = queue
        self._current_index = index
        self._current_track = track
        self._resume_position = position
        self._started = False
        artists = ', '.join(a.name for a in track.artists) if track.artists else ''
        try:
            np = self.screen.query_one(NowPlaying)
            np.track_title = track.title or ''
            np.track_artist = artists
            np.is_liked = self._client.is_liked(track)
            np.is_playing = False
            np.volume = self.player.volume
            np.set_progress(position, (track.duration_ms or 0) / 1000)
        except Exception:
            pass
        try:
            tl = self.screen.query_one(TrackList)
            tl.set_playing(index)
            tl.move_cursor(row=index, scroll=True)
        except Exception:
            pass
        self._fetch_cover(track)

    def _on_track_end(self) -> None:
        self.call_from_thread(self._handle_track_end)

    def _handle_track_end(self) -> None:
        # Report the play only when the track finished (change-reason: finish).
        self._report_play((self._current_track.duration_ms or 0) / 1000
                          if self._current_track else 0, change_reason='finish')
        if self._wave and self._current_track and self._current_track.id:
            tid = str(self._current_track.id)
            batch = self._wave_batches.get(tid)
            seconds = self.player.duration
            self.run_worker(
                lambda: self._client.wave_track_finished(tid, seconds, batch), thread=True
            )
        if self.repeat_mode == 'one' and self._current_track:
            self._start_track(self._current_track)
        else:
            self.next_track(skipped=False)

    def _safe_np(self, fn) -> None:
        try:
            fn(self.screen.query_one(NowPlaying))
        except Exception:
            pass


# ------------------------------------------------------------------
# Entry point
# ------------------------------------------------------------------

def _acquire_token() -> str:
    """Run OAuth Device Flow and save the resulting token to config."""
    from yandex_music import Client as _Client
    from ymtui.config import save_config, load_config

    def on_code(code):
        print(f'Откройте {code.verification_url}')
        print(f'и введите код: {code.user_code}')

    print('Токен не найден. Выполняется авторизация через Яндекс...')
    oauth = _Client().device_auth(on_code=on_code)
    token = oauth.access_token
    config = load_config()
    config['token'] = token
    save_config(config)
    print('Токен сохранён в ~/.config/ymtui/config.ini')
    return token


def main() -> None:
    token = get_token() or _acquire_token()
    YMPlayerApp(token).run()


if __name__ == '__main__':
    main()
