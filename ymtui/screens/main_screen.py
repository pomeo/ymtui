"""Main application screen — spotify-tui style layout.

Navigation is a two-level drill-down:

    Library (categories)  →  Collection (playlists/albums)  →  Songs (tracks)

Liked Songs and Chart load tracks straight into Songs.  Daily, New playlists,
New releases and My playlists fill the bottom Collection panel; picking an item
there loads its tracks into Songs.
"""
from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding, BindingsMap
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Footer, Static

from ymtui.api.client import YMClient
from ymtui.i18n import t
from ymtui.screens.help_screen import HelpScreen
from ymtui.widgets.library import Collection, Library
from ymtui.widgets.now_playing import NowPlaying
from ymtui.widgets.search import SearchBar
from ymtui.widgets.tracklist import TrackList


def build_main_bindings() -> list[Binding]:
    """Build the screen bindings with translated descriptions."""
    return [
        Binding('space', 'toggle_play', t('bind.play')),
        Binding('n', 'next_track', t('bind.next')),
        Binding('p', 'previous_track', t('bind.prev')),
        Binding('l', 'like', t('bind.like')),
        Binding('s', 'shuffle', t('bind.shuffle')),
        Binding('r', 'repeat', t('bind.repeat')),
        Binding('comma,less_than_sign', 'seek_back', t('bind.seekback')),
        Binding('full_stop,greater_than_sign', 'seek_forward', t('bind.seekfwd')),
        Binding('plus,equals_sign', 'volume_up', t('bind.volup')),
        Binding('minus', 'volume_down', t('bind.voldown')),
        Binding('slash', 'focus_search', t('bind.search')),
        Binding('tab', 'focus_panel(1)', 'Next panel', show=False),
        Binding('shift+tab', 'focus_panel(-1)', 'Prev panel', show=False),
        Binding('question_mark', 'help', t('bind.help')),
        Binding('q', 'quit', t('bind.quit')),
    ]


class MainScreen(Screen):
    # Panels cycled through with Tab / Shift+Tab.
    PANELS = ('#search', '#library', '#collection', '#tracklist')

    BINDINGS = build_main_bindings()

    # Metatag categories -> Yandex tree title.
    TREE_TITLES = {
        'genres': 'Жанры', 'moods': 'Настроения',
        'activities': 'Занятия', 'eras': 'Эпохи',
    }

    def __init__(self, client: YMClient, **kwargs) -> None:
        super().__init__(**kwargs)
        # Rebuild bindings for the current language (footer key hints).
        self._bindings = BindingsMap(build_main_bindings())
        self._client = client
        self._first_load = True
        self._collection_titlekey: str | None = None
        self._song_source: dict = {'type': 'liked'}

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def compose(self) -> ComposeResult:
        with Horizontal(id='top-row'):
            yield SearchBar(id='search')
            yield Static(t('hint.help'), id='help')
        with Horizontal(id='mid-row'):
            with Vertical(id='sidebar'):
                yield Library(id='library')
                yield Collection(id='collection')
            yield TrackList(id='tracklist')
        yield NowPlaying(id='now-playing')
        yield Footer()

    def on_mount(self) -> None:
        self.query_one('#help', Static).border_title = t('panel.help')
        np = self.query_one(NowPlaying)
        np.device = self._client.display_name
        # Reflect the real player/app state so the status bar isn't stale
        # (e.g. showing 80% before the first track sets the actual volume).
        np.volume = self.app.player.volume  # type: ignore[attr-defined]
        np.shuffle = self.app.shuffle  # type: ignore[attr-defined]
        np.repeat = self.app.repeat  # type: ignore[attr-defined]
        # Songs panel active on start, so the user can press play right away.
        self.query_one(TrackList).focus()
        self.query_one(Collection).loading = True

        # Restore last session: active category + Songs source.
        category = self.app.state.get('category') or 'liked'  # type: ignore[attr-defined]
        source = self.app.state.get('source') or {'type': 'liked'}  # type: ignore[attr-defined]
        self._song_source = source

        idx = Library.index_of(category)
        if idx is not None:
            self.query_one(Library).index = idx

        tag = self.app.state.get('tag')  # type: ignore[attr-defined]
        if category in self.TREE_TITLES and tag:
            # We were drilled into a metatag: reopen its playlists directly.
            self._open_tag(tag['tag'], tag['title'])
        elif category in Library.COLLECTION_CATEGORIES:
            self._open_collection(category)
        else:
            self._open_collection('my-playlists')  # sensible default content
        self._load_songs(source)

    # ------------------------------------------------------------------
    # Songs (right panel)
    # ------------------------------------------------------------------

    def _load_songs(self, source: dict, focus_request: bool = False,
                    autoplay: bool = False) -> None:
        if source.get('type') != 'wave':
            self.app.exit_wave()  # type: ignore[attr-defined]
        self.app.save_source(source)  # type: ignore[attr-defined]
        self._song_source = source
        self.query_one(TrackList).loading = True
        self.run_worker(
            lambda: self._fetch_songs(source, focus_request, autoplay), thread=True
        )

    def _fetch_songs(self, source: dict, focus_request: bool, autoplay: bool = False) -> None:
        kind = source.get('type')
        if kind == 'wave':
            tracks, batch_id = self._client.wave_batch()
            if batch_id:
                self._client.wave_radio_started(batch_id)
            liked_ids = self._client.liked_ids()
            self.app.call_from_thread(
                self._apply_wave, tracks, batch_id, liked_ids, focus_request, autoplay
            )
            return
        if kind == 'chart':
            tracks, title = self._client.chart(), t('songs.chart')
        elif kind == 'history':
            tracks, title = self._client.history_tracks(), t('songs.history')
        elif kind == 'playlist':
            tracks = self._client.playlist_tracks(source['kind'], source['user_id'])
            title = source.get('title', 'Playlist')
        elif kind == 'album':
            tracks = self._client.album_tracks(source['album_id'])
            title = source.get('title', 'Album')
        elif kind == 'search':
            query = source.get('query', '')
            tracks, title = self._client.search_tracks(query), t('songs.search', q=query)
        else:
            tracks, title = self._client.liked_tracks(), t('songs.liked')
        liked_ids = self._client.liked_ids()
        self.app.call_from_thread(self._apply_tracks, tracks, title, liked_ids, focus_request)
        self.app.call_from_thread(self._highlight_collection_item, source)

    def _apply_tracks(self, tracks, title, liked_ids, focus=False) -> None:
        """Populate Songs.

        Focus moves to Songs only on the very first load (so play is one
        keypress away at startup) or when explicitly requested (e.g. after a
        search). Plain sidebar navigation keeps focus where it is.
        """
        tl = self.query_one(TrackList)
        tl.load_tracks(tracks, title, liked_ids)
        if focus or self._first_load:
            tl.focus()
        if self._first_load:
            self._try_resume(tl)
        self._first_load = False

    def _apply_wave(self, tracks, batch_id, liked_ids, focus, autoplay) -> None:
        tl = self.query_one(TrackList)
        tl.load_tracks(tracks, t('songs.wave'), liked_ids)
        self.app.start_wave(batch_id, tracks)  # type: ignore[attr-defined]
        if focus or self._first_load:
            tl.focus()
        self._first_load = False
        self._highlight_collection_item(self._song_source)
        if autoplay and tracks:
            self.app.play_track(tracks[0], 0)  # type: ignore[attr-defined]

    def _try_resume(self, tl: TrackList) -> None:
        """On the first load, prime the last played track if it's in the list."""
        tid = self.app.state.get('track_id')  # type: ignore[attr-defined]
        if not tid:
            return
        position = float(self.app.state.get('position') or 0.0)  # type: ignore[attr-defined]
        for i, track in enumerate(tl.tracks):
            if str(track.id) == str(tid):
                self.app.prime_resume(track, i, position, tl.tracks)  # type: ignore[attr-defined]
                break

    # ------------------------------------------------------------------
    # Collection (bottom panel)
    # ------------------------------------------------------------------

    def _collection_title(self, category: str) -> str:
        if category == 'my-playlists':
            return t('coll.my-playlists')
        return t('cat.' + category)

    def _open_collection(self, category: str) -> None:
        self._collection_titlekey = category
        self.query_one(Collection).loading = True
        self.run_worker(lambda: self._fetch_collection(category), thread=True)

    def _fetch_collection(self, category: str) -> None:
        if category == 'daily':
            items = [self._playlist_item(p) for p in self._client.feed_playlists()]
        elif category == 'new-playlists':
            items = [self._playlist_item(p) for p in self._client.new_playlists()]
        elif category == 'new-releases':
            items = [self._album_item(a) for a in self._client.new_releases()]
        elif category in self.TREE_TITLES:
            tags = self._client.metatag_tags(self.TREE_TITLES[category])
            items = [{'type': 'tag', 'tag': tag, 'title': f'{name}  ›'} for tag, name in tags]
        else:  # my-playlists
            items = [self._playlist_item(p) for p in self._client.playlists()]
        self.app.call_from_thread(self._apply_collection, self._collection_title(category), items)

    def _open_tag(self, tag: str, title: str) -> None:
        """Drill from a metatag into its playlists (shown in the Collection)."""
        self._collection_titlekey = None  # title is the API tag name, not translatable
        self.app.save_tag({'tag': tag, 'title': title})  # type: ignore[attr-defined]
        self.query_one(Collection).loading = True
        self.run_worker(lambda: self._fetch_tag_playlists(tag, title), thread=True)

    def _fetch_tag_playlists(self, tag: str, title: str) -> None:
        items = [self._playlist_item(p) for p in self._client.metatag_playlists(tag)]
        self.app.call_from_thread(self._apply_collection, title, items)

    def _apply_collection(self, title: str, items: list[dict]) -> None:
        self.query_one(Collection).load_items(title, items)
        # Highlight after the async clear/append settles so indices line up.
        self.call_after_refresh(self._highlight_collection_item, self._song_source)

    def _highlight_collection_item(self, source: dict) -> None:
        col = self.query_one(Collection)
        col.index = next(
            (i for i, item in enumerate(col.items) if self._same_source(item, source)),
            None,
        )

    @staticmethod
    def _playlist_item(playlist) -> dict:
        uid = playlist.owner.uid if playlist.owner else None
        return {
            'type': 'playlist',
            'kind': playlist.kind,
            'user_id': str(uid),
            'title': playlist.title or 'Playlist',
        }

    @staticmethod
    def _album_item(album) -> dict:
        artists = ', '.join(a.name for a in (album.artists or []) if a.name)
        name = album.title or 'Album'
        return {
            'type': 'album',
            'album_id': album.id,
            'title': f'{name} — {artists}' if artists else name,
        }

    @staticmethod
    def _same_source(a: dict, b: dict) -> bool:
        if not b or a.get('type') != b.get('type'):
            return False
        if a['type'] == 'playlist':
            return (str(a.get('kind')) == str(b.get('kind'))
                    and str(a.get('user_id')) == str(b.get('user_id')))
        if a['type'] == 'album':
            return str(a.get('album_id')) == str(b.get('album_id'))
        return False

    def _set_active_category(self, category: str) -> None:
        self.app.save_category(category)  # type: ignore[attr-defined]
        self.app.save_tag(None)  # picking a category resets any metatag drill  # type: ignore[attr-defined]
        idx = Library.index_of(category)
        if idx is not None:
            self.query_one(Library).index = idx

    # ------------------------------------------------------------------
    # Message handlers
    # ------------------------------------------------------------------

    def on_library_category_selected(self, event: Library.CategorySelected) -> None:
        category = event.category
        self._set_active_category(category)
        if category == 'wave':
            self._load_songs({'type': 'wave'}, autoplay=True)
        elif category in ('liked', 'chart', 'history'):
            self._load_songs({'type': category})
        else:
            self._open_collection(category)

    def on_collection_item_selected(self, event: Collection.ItemSelected) -> None:
        source = event.source
        if source.get('type') == 'tag':
            # Drill one level deeper: show this tag's playlists in the Collection.
            self._open_tag(source['tag'], source['title'].rstrip(' ›'))
        else:
            self._load_songs(source)

    def on_search_bar_query(self, event: SearchBar.Query) -> None:
        # Focus moves to the results once they load (handled in _apply_tracks).
        self._load_songs({'type': 'search', 'query': event.query}, focus_request=True)

    def on_track_list_track_selected(self, event: TrackList.TrackSelected) -> None:
        self.app.play_track(event.track, event.index)  # type: ignore[attr-defined]

    def on_progress_line_clicked(self, event) -> None:
        self.app.seek_fraction(event.fraction)  # type: ignore[attr-defined]

    # ------------------------------------------------------------------
    # Localisation
    # ------------------------------------------------------------------

    def _songs_title(self, source: dict) -> str:
        kind = source.get('type')
        keys = {'liked': 'songs.liked', 'chart': 'songs.chart',
                'history': 'songs.history', 'wave': 'songs.wave'}
        if kind in keys:
            return t(keys[kind])
        if kind == 'search':
            return t('songs.search', q=source.get('query', ''))
        return source.get('title', '')  # playlist/album: API name, not translated

    def retranslate(self) -> None:
        """Re-apply all visible text after a language change (no reload)."""
        help_box = self.query_one('#help', Static)
        help_box.update(t('hint.help'))
        help_box.border_title = t('panel.help')
        self.query_one(Library).retranslate()
        self.query_one(SearchBar).retranslate()
        self.query_one(NowPlaying).retranslate()
        self.query_one(TrackList).retranslate()
        self.query_one(TrackList).retitle(self._songs_title(self._song_source))
        if self._collection_titlekey:
            self.query_one(Collection).border_title = self._collection_title(
                self._collection_titlekey
            )
        # Footer key hints
        self._bindings = BindingsMap(build_main_bindings())
        try:
            self.refresh_bindings()
            self.query_one(Footer).refresh(recompose=True)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Actions (keyboard bindings)
    # ------------------------------------------------------------------

    def action_toggle_play(self) -> None:
        self.app.toggle_play()  # type: ignore[attr-defined]

    def action_next_track(self) -> None:
        self.app.next_track()  # type: ignore[attr-defined]

    def action_previous_track(self) -> None:
        self.app.previous_track()  # type: ignore[attr-defined]

    def action_like(self) -> None:
        self.app.toggle_like_current()  # type: ignore[attr-defined]

    def action_shuffle(self) -> None:
        self.app.toggle_shuffle()  # type: ignore[attr-defined]

    def action_repeat(self) -> None:
        self.app.toggle_repeat()  # type: ignore[attr-defined]

    def action_seek_back(self) -> None:
        self.app.seek(-5)  # type: ignore[attr-defined]

    def action_seek_forward(self) -> None:
        self.app.seek(5)  # type: ignore[attr-defined]

    def action_volume_up(self) -> None:
        self.app.change_volume(5)  # type: ignore[attr-defined]

    def action_volume_down(self) -> None:
        self.app.change_volume(-5)  # type: ignore[attr-defined]

    def action_focus_search(self) -> None:
        self.query_one(SearchBar).focus()

    def action_focus_panel(self, step: int) -> None:
        panels = [self.query_one(sel) for sel in self.PANELS]
        try:
            idx = panels.index(self.focused)
        except ValueError:
            idx = -1 if step > 0 else 0
        panels[(idx + step) % len(panels)].focus()

    def action_help(self) -> None:
        self.app.push_screen(HelpScreen())

    def action_quit(self) -> None:
        self.app.exit()
