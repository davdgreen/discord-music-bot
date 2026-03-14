from __future__ import annotations
import io
import logging
from typing import Optional, TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from core.queue import RepeatMode
from core.track import Track
from utils.checks import ensure_in_voice, ensure_same_voice, NotInVoice, NotSameVoice
from utils.embeds import (
    error_embed, success_embed, now_playing_embed, queue_embed,
    history_embed, export_text,
)
from utils.time_fmt import hms_to_seconds, seconds_to_hms

if TYPE_CHECKING:
    from bot import MusicBot

log = logging.getLogger(__name__)

_SPOTIFY_RE = __import__("re").compile(r"https?://open\.spotify\.com/")


class MusicCog(commands.Cog):
    def __init__(self, bot: "MusicBot") -> None:
        self.bot = bot

    async def cog_app_command_error(
        self,
        interaction: discord.Interaction,
        error: app_commands.AppCommandError,
    ) -> None:
        msg = str(error)
        if isinstance(error, (NotInVoice, NotSameVoice)):
            pass
        elif isinstance(error, app_commands.CommandInvokeError):
            msg = str(error.original)
        try:
            if interaction.response.is_done():
                await interaction.followup.send(embed=error_embed(msg), ephemeral=True)
            else:
                await interaction.response.send_message(embed=error_embed(msg), ephemeral=True)
        except discord.HTTPException:
            pass

    @app_commands.command(name="join", description="Join your voice channel.")
    async def join(self, interaction: discord.Interaction) -> None:
        channel = ensure_in_voice(interaction)
        player = self.bot.get_player(interaction.guild_id)
        ensure_same_voice(interaction, player.voice_client)
        await player.join(channel)
        await interaction.response.send_message(
            embed=success_embed(f"Joined **{channel.name}**."), ephemeral=True
        )

    @app_commands.command(name="leave", description="Disconnect from voice.")
    async def leave(self, interaction: discord.Interaction) -> None:
        player = self.bot.get_player(interaction.guild_id)
        if not player.voice_client or not player.voice_client.is_connected():
            await interaction.response.send_message(
                embed=error_embed("I'm not in a voice channel."), ephemeral=True
            )
            return
        await player.leave()
        await interaction.response.send_message(
            embed=success_embed("Disconnected."), ephemeral=True
        )

    @app_commands.command(name="play", description="Play a YouTube URL, search query, or Spotify URL.")
    @app_commands.describe(query="YouTube URL / search term / Spotify URL")
    async def play(self, interaction: discord.Interaction, query: str) -> None:
        channel = ensure_in_voice(interaction)
        player = self.bot.get_player(interaction.guild_id)
        ensure_same_voice(interaction, player.voice_client)

        await interaction.response.defer()

        if not player.voice_client or not player.voice_client.is_connected():
            await player.join(channel)

        player._np_channel = interaction.channel  # type: ignore[attr-defined]

        if _SPOTIFY_RE.match(query):
            if not self.bot.spotify:
                await interaction.followup.send(
                    embed=error_embed("Spotify support is not configured.")
                )
                return
            try:
                tracks = await self.bot.spotify.resolve(query, self.bot.loop)
            except Exception as exc:
                await interaction.followup.send(embed=error_embed(f"Spotify error: {exc}"))
                return
            for track in tracks:
                await player.add_and_play(track)
            await interaction.followup.send(
                embed=success_embed(f"Enqueued **{len(tracks)}** track(s) from Spotify.")
            )
            return

        track = Track(title=query, webpage_url=query)
        await player.add_and_play(track)

        if player.queue.current and player.queue.current.title != query:
            await interaction.followup.send(
                embed=now_playing_embed(player.queue.current, player.queue)
            )
        else:
            await interaction.followup.send(
                embed=success_embed(f"Added to queue: **{query}**")
            )

    @app_commands.command(name="pause", description="Pause playback.")
    async def pause(self, interaction: discord.Interaction) -> None:
        player = self.bot.get_player(interaction.guild_id)
        if await player.pause():
            await interaction.response.send_message(embed=success_embed("Paused."))
        else:
            await interaction.response.send_message(
                embed=error_embed("Nothing is playing."), ephemeral=True
            )

    @app_commands.command(name="resume", description="Resume playback.")
    async def resume(self, interaction: discord.Interaction) -> None:
        player = self.bot.get_player(interaction.guild_id)
        if await player.resume():
            await interaction.response.send_message(embed=success_embed("Resumed."))
        else:
            await interaction.response.send_message(
                embed=error_embed("Nothing is paused."), ephemeral=True
            )

    @app_commands.command(name="stop", description="Stop playback and clear the queue.")
    async def stop(self, interaction: discord.Interaction) -> None:
        player = self.bot.get_player(interaction.guild_id)
        await player.stop()
        await interaction.response.send_message(embed=success_embed("Stopped and cleared queue."))

    @app_commands.command(name="skip", description="Skip the current track.")
    async def skip(self, interaction: discord.Interaction) -> None:
        player = self.bot.get_player(interaction.guild_id)
        if not player.queue.current:
            await interaction.response.send_message(
                embed=error_embed("Nothing is playing."), ephemeral=True
            )
            return
        skipped = await player.skip()
        title = skipped.title if skipped else "track"
        await interaction.response.send_message(embed=success_embed(f"Skipped **{title}**."))

    @app_commands.command(name="nowplaying", description="Show the currently playing track.")
    async def nowplaying(self, interaction: discord.Interaction) -> None:
        player = self.bot.get_player(interaction.guild_id)
        if not player.queue.current:
            await interaction.response.send_message(
                embed=error_embed("Nothing is playing."), ephemeral=True
            )
            return
        await interaction.response.send_message(
            embed=now_playing_embed(player.queue.current, player.queue)
        )

    @app_commands.command(name="seek", description="Seek to a position (e.g. 1:30 or 90).")
    @app_commands.describe(timestamp="Position to seek to (H:MM:SS, M:SS, or seconds)")
    async def seek(self, interaction: discord.Interaction, timestamp: str) -> None:
        player = self.bot.get_player(interaction.guild_id)
        if not player.queue.current:
            await interaction.response.send_message(
                embed=error_embed("Nothing is playing."), ephemeral=True
            )
            return
        try:
            seconds = hms_to_seconds(timestamp)
        except ValueError:
            await interaction.response.send_message(
                embed=error_embed(f"Invalid timestamp: `{timestamp}`"), ephemeral=True
            )
            return

        current = player.queue.current
        warn = ""
        if current.duration and seconds >= current.duration:
            seconds = current.duration - 1
            warn = f" (clamped to {seconds_to_hms(seconds)})"

        await interaction.response.defer()
        await player.seek(seconds)
        await interaction.followup.send(
            embed=success_embed(f"Seeked to **{seconds_to_hms(seconds)}**{warn}.")
        )

    @app_commands.command(name="forward", description="Seek forward N seconds (default 10).")
    @app_commands.describe(seconds="Seconds to skip forward")
    async def forward(self, interaction: discord.Interaction, seconds: int = 10) -> None:
        player = self.bot.get_player(interaction.guild_id)
        current = player.queue.current
        if not current:
            await interaction.response.send_message(
                embed=error_embed("Nothing is playing."), ephemeral=True
            )
            return
        new_pos = (current.seek_offset or 0) + seconds
        await interaction.response.defer()
        await player.seek(new_pos)
        await interaction.followup.send(
            embed=success_embed(f"Forwarded **{seconds}s** -> `{seconds_to_hms(new_pos)}`.")
        )

    @app_commands.command(name="rewind", description="Seek back N seconds (default 10).")
    @app_commands.describe(seconds="Seconds to rewind")
    async def rewind(self, interaction: discord.Interaction, seconds: int = 10) -> None:
        player = self.bot.get_player(interaction.guild_id)
        current = player.queue.current
        if not current:
            await interaction.response.send_message(
                embed=error_embed("Nothing is playing."), ephemeral=True
            )
            return
        new_pos = max(0, (current.seek_offset or 0) - seconds)
        await interaction.response.defer()
        await player.seek(new_pos)
        await interaction.followup.send(
            embed=success_embed(f"Rewound **{seconds}s** -> `{seconds_to_hms(new_pos)}`.")
        )

    @app_commands.command(name="restart", description="Restart the current track from the beginning.")
    async def restart(self, interaction: discord.Interaction) -> None:
        player = self.bot.get_player(interaction.guild_id)
        if not player.queue.current:
            await interaction.response.send_message(
                embed=error_embed("Nothing is playing."), ephemeral=True
            )
            return
        await interaction.response.defer()
        await player.seek(0)
        await interaction.followup.send(embed=success_embed("Restarted track."))

    @app_commands.command(name="queue", description="Show the current queue.")
    @app_commands.describe(page="Page number")
    async def queue_cmd(self, interaction: discord.Interaction, page: int = 1) -> None:
        player = self.bot.get_player(interaction.guild_id)
        await interaction.response.send_message(embed=queue_embed(player.queue, page))

    @app_commands.command(name="remove", description="Remove a track from the queue by its position.")
    @app_commands.describe(index="1-based position in the queue")
    async def remove(self, interaction: discord.Interaction, index: int) -> None:
        player = self.bot.get_player(interaction.guild_id)
        if index == 0:
            await self.skip.callback(self, interaction)
            return
        try:
            removed = player.queue.remove(index)
        except IndexError as exc:
            await interaction.response.send_message(embed=error_embed(str(exc)), ephemeral=True)
            return
        await interaction.response.send_message(
            embed=success_embed(f"Removed **{removed.title}** from the queue.")
        )

    @app_commands.command(name="clear", description="Clear the entire queue (does not stop current track).")
    async def clear(self, interaction: discord.Interaction) -> None:
        player = self.bot.get_player(interaction.guild_id)
        player.queue.clear()
        await interaction.response.send_message(embed=success_embed("Queue cleared."))

    @app_commands.command(name="move", description="Move a track within the queue.")
    @app_commands.describe(from_pos="Current position (1-based)", to_pos="Target position (1-based)")
    async def move(self, interaction: discord.Interaction, from_pos: int, to_pos: int) -> None:
        player = self.bot.get_player(interaction.guild_id)
        try:
            player.queue.move(from_pos, to_pos)
        except IndexError as exc:
            await interaction.response.send_message(embed=error_embed(str(exc)), ephemeral=True)
            return
        await interaction.response.send_message(
            embed=success_embed(f"Moved track from position **{from_pos}** to **{to_pos}**.")
        )

    @app_commands.command(name="repeat", description="Set repeat mode.")
    @app_commands.describe(mode="off / one / all")
    @app_commands.choices(mode=[
        app_commands.Choice(name="Off", value="off"),
        app_commands.Choice(name="Repeat One", value="one"),
        app_commands.Choice(name="Repeat All", value="all"),
    ])
    async def repeat(self, interaction: discord.Interaction, mode: str) -> None:
        player = self.bot.get_player(interaction.guild_id)
        player.queue.repeat = RepeatMode(mode)
        await interaction.response.send_message(
            embed=success_embed(f"Repeat mode set to **{mode}**.")
        )

    @app_commands.command(name="shuffle", description="Shuffle the queue.")
    async def shuffle(self, interaction: discord.Interaction) -> None:
        player = self.bot.get_player(interaction.guild_id)
        if len(player.queue) == 0:
            await interaction.response.send_message(
                embed=error_embed("Queue is empty."), ephemeral=True
            )
            return
        player.queue.shuffle()
        await interaction.response.send_message(embed=success_embed("Queue shuffled."))

    @app_commands.command(name="reshuffle", description="Re-randomize the shuffled queue.")
    async def reshuffle(self, interaction: discord.Interaction) -> None:
        player = self.bot.get_player(interaction.guild_id)
        if len(player.queue) == 0:
            await interaction.response.send_message(
                embed=error_embed("Queue is empty."), ephemeral=True
            )
            return
        player.queue.shuffle()
        await interaction.response.send_message(embed=success_embed("Queue reshuffled."))

    @app_commands.command(name="history", description="Show recently played tracks.")
    @app_commands.describe(count="Number of tracks to show (max 50)")
    async def history(self, interaction: discord.Interaction, count: int = 10) -> None:
        player = self.bot.get_player(interaction.guild_id)
        tracks = player.queue.history(min(count, 50))
        await interaction.response.send_message(embed=history_embed(tracks))

    @app_commands.command(name="export", description="Export the queue as a text file.")
    async def export(self, interaction: discord.Interaction) -> None:
        player = self.bot.get_player(interaction.guild_id)
        text = export_text(player.queue)
        buf = io.BytesIO(text.encode())
        await interaction.response.send_message(
            file=discord.File(buf, filename="queue.txt"),
            ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(MusicCog(bot))
