from __future__ import annotations
import asyncio
import logging
import re
from typing import Optional

import spotipy
from spotipy.oauth2 import SpotifyClientCredentials

from core.track import Track

log = logging.getLogger(__name__)

_TRACK_RE = re.compile(r"spotify\.com/track/([A-Za-z0-9]+)")
_ALBUM_RE = re.compile(r"spotify\.com/album/([A-Za-z0-9]+)")
_PLAYLIST_RE = re.compile(r"spotify\.com/playlist/([A-Za-z0-9]+)")


def _stub(title: str, artist: str) -> Track:
    query = f"ytsearch:{title} {artist} audio"
    return Track(title=f"{title} - {artist}", webpage_url=query)


class SpotifyResolver:
    def __init__(self, client_id: str, client_secret: str) -> None:
        self._sp = spotipy.Spotify(
            auth_manager=SpotifyClientCredentials(
                client_id=client_id,
                client_secret=client_secret,
            )
        )

    async def resolve(
        self, url: str, loop: Optional[asyncio.AbstractEventLoop] = None
    ) -> list[Track]:
        loop = loop or asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._resolve_sync, url)

    def _resolve_sync(self, url: str) -> list[Track]:
        if m := _TRACK_RE.search(url):
            return self._track(m.group(1))
        if m := _ALBUM_RE.search(url):
            return self._album(m.group(1))
        if m := _PLAYLIST_RE.search(url):
            return self._playlist(m.group(1))
        raise ValueError(f"Unrecognised Spotify URL: {url}")

    def _track(self, track_id: str) -> list[Track]:
        data = self._sp.track(track_id)
        title = data["name"]
        artist = data["artists"][0]["name"]
        return [_stub(title, artist)]

    def _album(self, album_id: str) -> list[Track]:
        data = self._sp.album_tracks(album_id)
        tracks: list[Track] = []
        while True:
            for item in data["items"]:
                title = item["name"]
                artist = item["artists"][0]["name"]
                tracks.append(_stub(title, artist))
            if data["next"]:
                data = self._sp.next(data)
            else:
                break
        return tracks

    def _playlist(self, playlist_id: str) -> list[Track]:
        data = self._sp.playlist_items(
            playlist_id,
            fields="items(track(name,artists(name))),next",
        )
        tracks: list[Track] = []
        while True:
            for item in data["items"]:
                t = item.get("track")
                if not t:
                    continue
                title = t["name"]
                artist = t["artists"][0]["name"]
                tracks.append(_stub(title, artist))
            if data.get("next"):
                data = self._sp.next(data)
            else:
                break
        return tracks
