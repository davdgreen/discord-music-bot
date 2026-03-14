from __future__ import annotations
import asyncio
import logging
from typing import Optional

import discord
import yt_dlp

from core.track import Track

log = logging.getLogger(__name__)

YTDL_OPTIONS: dict = {
    "format": "bestaudio/best",
    "quiet": True,
    "no_warnings": True,
    "default_search": "ytsearch",
    "source_address": "0.0.0.0",
    "noplaylist": True,
    "extract_flat": False,
}

FFMPEG_BEFORE_OPTIONS = "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5"


class FFmpegYTDLSource:
    @staticmethod
    async def create(
        track: Track,
        loop: Optional[asyncio.AbstractEventLoop] = None,
    ) -> tuple[discord.FFmpegOpusAudio, Track]:
        loop = loop or asyncio.get_event_loop()
        ytdl = yt_dlp.YoutubeDL(YTDL_OPTIONS)

        data = await loop.run_in_executor(
            None,
            lambda: ytdl.extract_info(track.webpage_url, download=False),
        )

        if "entries" in data:
            data = data["entries"][0]

        stream_url: str = data["url"]
        duration: Optional[int] = data.get("duration")
        thumbnail: Optional[str] = data.get("thumbnail")
        uploader: Optional[str] = data.get("uploader") or data.get("channel")
        title: str = data.get("title", track.title)

        resolved = Track(
            title=title,
            webpage_url=data.get("webpage_url", track.webpage_url),
            duration=duration,
            thumbnail=thumbnail,
            uploader=uploader,
            seek_offset=track.seek_offset,
        )

        seek_options = ""
        if track.seek_offset > 0:
            seek_options = f" -ss {track.seek_offset}"

        audio = discord.FFmpegOpusAudio(
            stream_url,
            before_options=FFMPEG_BEFORE_OPTIONS + seek_options,
        )

        return audio, resolved
