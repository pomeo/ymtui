"""Thin wrapper around yandex-music Client."""
from __future__ import annotations

import datetime
from typing import Optional

from yandex_music import Client, Playlist, Track


class YMClient:
    WAVE_STATION = 'user:onyourwave'  # «Моя волна» personal radio

    def __init__(self, token: str) -> None:
        self._client = Client(token).init()
        self._liked_ids: set[str] | None = None
        self._metatags = None
        self._metatags_fetched = False
        self._chart_item: str | None = None  # owner:kind плейлиста-чарта

    # ------------------------------------------------------------------
    # Account
    # ------------------------------------------------------------------

    @property
    def account(self):
        return self._client.me.account

    @property
    def display_name(self) -> str:
        acc = self.account
        return acc.display_name or acc.login or 'ymtui'

    # ------------------------------------------------------------------
    # Track collections
    # ------------------------------------------------------------------

    def liked_tracks(self) -> list[Track]:
        likes = self._client.users_likes_tracks()
        if not likes:
            return []
        # fetch_tracks() resolves the short references into full Track objects
        try:
            tracks = likes.fetch_tracks()
        except Exception:
            tracks = [t.track for t in likes if t.track]
        self._liked_ids = {str(t.id) for t in tracks if t.id}
        return tracks

    def liked_ids(self) -> set[str]:
        """Return the set of liked track ids (cached, lazily fetched)."""
        if self._liked_ids is None:
            try:
                likes = self._client.users_likes_tracks()
                self._liked_ids = {str(t.id) for t in (likes or [])}
            except Exception:
                self._liked_ids = set()
        return self._liked_ids

    def playlists(self) -> list[Playlist]:
        return self._client.users_playlists_list() or []

    def feed_playlists(self) -> list[Playlist]:
        """Smart 'Daily' playlists from the personal feed (Плейлист дня, Дежавю…)."""
        try:
            feed = self._client.feed()
        except Exception:
            return []
        out: list[Playlist] = []
        for generated in (feed.generated_playlists or []):
            playlist = getattr(generated, 'data', None)
            if playlist is not None and getattr(playlist, 'kind', None) is not None:
                out.append(playlist)
        return out

    def new_playlists(self) -> list[Playlist]:
        """Editorial 'new playlists' from the landing page."""
        return self._landing_entities('new-playlists', 'kind')

    def new_releases(self):
        """New album releases from the landing page (list of Album)."""
        return self._landing_entities('new-releases', 'id')

    def _landing_entities(self, block: str, id_attr: str) -> list:
        try:
            result = self._client.landing(blocks=[block])
        except Exception:
            return []
        if not result or not result.blocks:
            return []
        out = []
        for b in result.blocks:
            for entity in (b.entities or []):
                data = entity.data
                if data is not None and getattr(data, id_attr, None) is not None:
                    out.append(data)
        return out

    def metatag_tags(self, tree_title: str) -> list[tuple[str, str]]:
        """Return (tag_id, title) pairs for a metatag tree (Genres/Moods/…)."""
        if not self._metatags_fetched:
            try:
                self._metatags = self._client.metatags()
            except Exception:
                self._metatags = None
            self._metatags_fetched = True
        trees = (self._metatags.trees if self._metatags else None) or []
        for tree in trees:
            if tree.title == tree_title:
                return [
                    (leaf.tag, leaf.title)
                    for leaf in (tree.leaves or [])
                    if getattr(leaf, 'tag', None)
                ]
        return []

    def metatag_playlists(self, tag: str, limit: int = 30) -> list[Playlist]:
        """Playlists for a metatag (e.g. 'Джаз')."""
        try:
            result = self._client.metatag_playlists(tag, limit=limit)
        except Exception:
            return []
        return (result.playlists or []) if result else []

    def album_tracks(self, album_id) -> list[Track]:
        """Full track list of an album (flattened across volumes/discs)."""
        try:
            album = self._client.albums_with_tracks(album_id)
        except Exception:
            return []
        tracks: list[Track] = []
        for volume in (album.volumes or []):
            tracks.extend(volume)
        return tracks

    def playlist_tracks(self, kind: int | str, user_id: Optional[str] = None) -> list[Track]:
        # A playlist that was deleted server-side raises here — treat as empty.
        try:
            uid = user_id or self._client.me.account.uid
            playlist = self._client.users_playlists(kind=kind, user_id=uid)
        except Exception:
            return []
        if not playlist or not playlist.tracks:
            return []
        # Short references inside a playlist need resolving into full Tracks
        try:
            return [ts.fetch_track() for ts in playlist.tracks]
        except Exception:
            return [t.track for t in playlist.tracks if t.track]

    def chart(self, region: str = 'russia') -> list[Track]:
        result = self._client.chart(region)
        if not result or not result.chart:
            self._chart_item = None
            return []
        ch = result.chart
        owner = getattr(getattr(ch, 'owner', None), 'uid', None)
        kind = getattr(ch, 'kind', None)
        # Чарт — это плейлист; его owner:kind нужен как context-item.
        self._chart_item = f'{owner}:{kind}' if owner and kind else None
        return [t.track for t in (ch.tracks or []) if t.track]

    @property
    def chart_item(self) -> str | None:
        return self._chart_item

    # ------------------------------------------------------------------
    # «Моя волна» — personal infinite radio (rotor station)
    # ------------------------------------------------------------------

    def wave_batch(self, queue: Optional[str] = None) -> tuple[list[Track], Optional[str]]:
        """Return (tracks, batch_id) for the next wave batch.

        ``queue`` is the id of the last played track, used to continue the
        stream; pass ``None`` to start a fresh wave.
        """
        try:
            result = self._client.rotor_station_tracks(self.WAVE_STATION, queue=queue)
        except Exception:
            return [], None
        if not result:
            return [], None
        tracks = [s.track for s in (result.sequence or []) if s.track]
        return tracks, result.batch_id

    def wave_radio_started(self, batch_id: Optional[str]) -> None:
        try:
            self._client.rotor_station_feedback_radio_started(
                self.WAVE_STATION, from_='ymtui', batch_id=batch_id
            )
        except Exception:
            pass

    def wave_track_started(self, track_id: str, batch_id: Optional[str]) -> None:
        try:
            self._client.rotor_station_feedback_track_started(
                self.WAVE_STATION, track_id, batch_id=batch_id
            )
        except Exception:
            pass

    def wave_track_finished(self, track_id: str, seconds: float, batch_id: Optional[str]) -> None:
        try:
            self._client.rotor_station_feedback_track_finished(
                self.WAVE_STATION, track_id, total_played_seconds=float(seconds or 0),
                batch_id=batch_id,
            )
        except Exception:
            pass

    def wave_skip(self, track_id: str, seconds: float, batch_id: Optional[str]) -> None:
        try:
            self._client.rotor_station_feedback_skip(
                self.WAVE_STATION, track_id, total_played_seconds=float(seconds or 0),
                batch_id=batch_id,
            )
        except Exception:
            pass

    def history_tracks(self, limit: int = 50) -> list[Track]:
        """Recently played tracks, most-recent first."""
        try:
            history = self._client.music_history(full_models_count=limit)
        except Exception:
            return []
        ids: list[str] = []
        for tab in (history.history_tabs or []) if history else []:
            for group in (tab.items or []):
                for item in (group.tracks or []):
                    if getattr(item, 'type', None) != 'track':
                        continue
                    item_id = getattr(item.data, 'item_id', None)
                    tid = getattr(item_id, 'track_id', None) if item_id else None
                    if tid and str(tid) not in ids:
                        ids.append(str(tid))
        ids = ids[:limit]
        if not ids:
            return []
        try:
            tracks = self._client.tracks(ids)
        except Exception:
            return []
        by_id = {str(t.id): t for t in tracks if t and t.id}
        return [by_id[i] for i in ids if i in by_id]

    def search_tracks(self, query: str, limit: int = 50) -> list[Track]:
        if not query.strip():
            return []
        try:
            result = self._client.search(query, type_='track', nocorrect=False)
        except Exception:
            return []
        if not result or not result.tracks or not result.tracks.results:
            return []
        return list(result.tracks.results)[:limit]

    # ------------------------------------------------------------------
    # Likes
    # ------------------------------------------------------------------

    def toggle_like(self, track: Track) -> bool:
        """Like or unlike a track. Returns the new liked state."""
        tid = str(track.id)
        liked = self.liked_ids()
        try:
            if tid in liked:
                track.dislike()
                liked.discard(tid)
                return False
            track.like()
            liked.add(tid)
            return True
        except Exception:
            return tid in liked

    def is_liked(self, track: Track) -> bool:
        return str(track.id) in self.liked_ids()

    # ------------------------------------------------------------------
    # Streaming
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Play reporting (как официальный клиент — для истории/статистики)
    # ------------------------------------------------------------------

    def report_play(self, track: Track, from_: str, played_seconds: float,
                    length_seconds: float, playlist_id: Optional[str] = None,
                    play_id: Optional[str] = None, change_reason: Optional[str] = None,
                    context: Optional[str] = None, context_item: Optional[str] = None,
                    batch_id: Optional[str] = None) -> None:
        """Send a play-audio event (the request the official client makes).

        Built manually (not via ``Client.play_audio``) so we can include the
        ``context`` / ``context-item`` / ``change-reason`` fields — without the
        context the play is accepted but never lands in listening history.
        """
        try:
            album_id = str(track.albums[0].id) if track.albums else None
            if not album_id or not getattr(track, 'id', None):
                return
            now = (datetime.datetime.now(datetime.timezone.utc)
                   .isoformat(timespec='milliseconds').replace('+00:00', 'Z'))
            played = int(max(0.0, played_seconds))
            data = {
                'track-id': str(track.id),
                'album-id': album_id,
                'from-cache': 'false',
                'from': from_,
                'play-id': play_id or '',
                'uid': self._client.me.account.uid,
                'timestamp': now,
                'client-now': now,
                'track-length-seconds': int(length_seconds or 0),
                'total-played-seconds': played,
                'end-position-seconds': played,
            }
            if context:
                data['context'] = context
            if context_item:
                data['context-item'] = context_item
            if playlist_id:
                data['playlist-id'] = playlist_id
            if batch_id:
                data['batch-id'] = batch_id  # для радио («Моя волна»)
            if change_reason:
                data['change-reason'] = change_reason
            self._client._request.post(f'{self._client.base_url}/play-audio', data)
        except Exception:
            pass

    def get_stream_url(self, track: Track) -> Optional[str]:
        """Return the best available direct stream URL for a track."""
        try:
            info_list = track.get_download_info(get_direct_links=True)
            mp3_options = [i for i in info_list if i.codec == 'mp3']
            if mp3_options:
                best = max(mp3_options, key=lambda x: x.bitrate_in_kbps)
                return best.direct_link
            if info_list:
                return info_list[0].direct_link
        except Exception:
            return None
        return None
