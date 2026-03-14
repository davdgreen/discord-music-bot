from __future__ import annotations
import asyncio
import logging
from typing import Optional, TYPE_CHECKING

import discord

from core.queue import TrackQueue, RepeatMode
from core.track import Track
from core.audio_source import FFmpegYTDLSource

if TYPE_CHECKING:
    from bot import MusicBot

log = logging.getLogger(__name__)

INACTIVITY_TIMEOUT = 300
MAX_SKIP_DEPTH = 5


class GuildPlayer:
    def __init__(self, bot: "MusicBot", guild: discord.Guild) -> None:
        self.bot = bot
        self.guild = guild
        self.queue = TrackQueue()
        self.voice_client: Optional[discord.VoiceClient] = None
        self._now_playing_msg: Optional[discord.Message] = None
        self._inactivity_task: Optional[asyncio.Task] = None
        self._playing = asyncio.Event()

    async def join(self, channel: discord.VoiceChannel) -> None:
        if self.voice_client and self.voice_client.is_connected():
            await self.voice_client.move_to(channel)
        else:
            self.voice_client = await channel.connect()
        self._cancel_inactivity()

    async def leave(self) -> None:
        self._cancel_inactivity()
        if self.voice_client:
            await self.voice_client.disconnect()
            self.voice_client = None
        self.queue.clear()
        self.queue.current = None
        await self._delete_now_playing()

    def on_voice_disconnect(self) -> None:
        self.voice_client = None
        self.queue.current = None
        self._cancel_inactivity()

    async def add_and_play(self, track: Track) -> None:
        self.queue.add(track)
        if self.voice_client and not self.voice_client.is_playing():
            await self.play_next()

    async def play_next(self, depth: int = 0) -> None:
        if depth >= MAX_SKIP_DEPTH:
            log.error("Too many consecutive yt-dlp failures; stopping playback.")
            return

        if not self.voice_client or not self.voice_client.is_connected():
            return

        track = self.queue.pop_next()
        if track is None:
            await self._delete_now_playing()
            self._start_inactivity_timer()
            return

        try:
            source, resolved = await FFmpegYTDLSource.create(track, self.bot.loop)
            self.queue.current = resolved
        except Exception as exc:
            log.warning("Failed to load %s: %s - skipping", track.title, exc)
            await self._notify_skip_error(track, exc)
            await self.play_next(depth + 1)
            return

        self.voice_client.play(
            source,
            after=lambda err: self._after_play(err),
        )
        await self._update_now_playing(resolved)
        self._cancel_inactivity()

    def _after_play(self, error: Optional[Exception]) -> None:
        if error:
            log.warning("Playback error: %s", error)
        asyncio.run_coroutine_threadsafe(self.play_next(), self.bot.loop)

    async def pause(self) -> bool:
        if self.voice_client and self.voice_client.is_playing():
            self.voice_client.pause()
            return True
        return False

    async def resume(self) -> bool:
        if self.voice_client and self.voice_client.is_paused():
            self.voice_client.resume()
            return True
        return False

    async def stop(self) -> None:
        self.queue.clear()
        self.queue.current = None
        if self.voice_client and (
            self.voice_client.is_playing() or self.voice_client.is_paused()
        ):
            self.voice_client.stop()
        await self._delete_now_playing()
        self._start_inactivity_timer()

    async def skip(self) -> Optional[Track]:
        skipped = self.queue.current
        if self.voice_client and (
            self.voice_client.is_playing() or self.voice_client.is_paused()
        ):
            self.voice_client.stop()
        else:
            await self.play_next()
        return skipped

    async def seek(self, seconds: int) -> None:
        current = self.queue.current
        if current is None:
            return
        if current.duration is not None:
            seconds = max(0, min(seconds, current.duration - 1))
        seeked = current.with_seek(seconds)
        self.queue.add_front(seeked)
        if self.voice_client and (
            self.voice_client.is_playing() or self.voice_client.is_paused()
        ):
            self.queue.current = None
            self.voice_client.stop()
        else:
            await self.play_next()

    async def _update_now_playing(
        self, track: Track, channel: Optional[discord.TextChannel] = None
    ) -> None:
        from utils.embeds import now_playing_embed
        embed = now_playing_embed(track, self.queue)
        try:
            if self._now_playing_msg:
                await self._now_playing_msg.edit(embed=embed)
            elif channel:
                self._now_playing_msg = await channel.send(embed=embed)
        except discord.HTTPException:
            self._now_playing_msg = None

    async def set_np_channel(self, channel: discord.TextChannel) -> None:
        self._np_channel = channel

    async def send_now_playing(self, channel: discord.TextChannel) -> None:
        from utils.embeds import now_playing_embed
        if self.queue.current is None:
            return
        embed = now_playing_embed(self.queue.current, self.queue)
        self._now_playing_msg = await channel.send(embed=embed)

    async def _delete_now_playing(self) -> None:
        if self._now_playing_msg:
            try:
                await self._now_playing_msg.delete()
            except discord.HTTPException:
                pass
            self._now_playing_msg = None

    async def _notify_skip_error(self, track: Track, exc: Exception) -> None:
        channel = getattr(self, "_np_channel", None)
        if channel:
            try:
                await channel.send(
                    f":warning: Skipping **{track.title}** - could not load: `{exc}`",
                    delete_after=15,
                )
            except discord.HTTPException:
                pass

    def _start_inactivity_timer(self) -> None:
        self._cancel_inactivity()
        self._inactivity_task = asyncio.create_task(self._inactivity_loop())

    def _cancel_inactivity(self) -> None:
        if self._inactivity_task and not self._inactivity_task.done():
            self._inactivity_task.cancel()
        self._inactivity_task = None

    async def _inactivity_loop(self) -> None:
        try:
            elapsed = 0
            while elapsed < INACTIVITY_TIMEOUT:
                await asyncio.sleep(60)
                elapsed += 60
                if not self.voice_client or not self.voice_client.is_connected():
                    return
                if self.voice_client.is_playing():
                    return
                members = [
                    m for m in self.voice_client.channel.members
                    if not m.bot
                ]
                if members:
                    elapsed = 0
            log.info("Auto-disconnecting from %s (inactivity)", self.guild.name)
            await self.leave()
        except asyncio.CancelledError:
            pass
