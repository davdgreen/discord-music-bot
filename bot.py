from __future__ import annotations
import asyncio
import logging
from typing import Optional

import discord
from discord.ext import commands

import config
from core.player import GuildPlayer
from core.spotify import SpotifyResolver

log = logging.getLogger(__name__)

COGS = [
    "cogs.music",
    "cogs.admin",
]


class MusicBot(commands.Bot):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.voice_states = True
        intents.guilds = True
        super().__init__(
            command_prefix=commands.when_mentioned,
            intents=intents,
            help_command=None,
        )
        self.guild_players: dict[int, GuildPlayer] = {}
        self.spotify: Optional[SpotifyResolver] = None

    def get_player(self, guild_id: int) -> GuildPlayer:
        if guild_id not in self.guild_players:
            guild = self.get_guild(guild_id)
            assert guild, f"Guild {guild_id} not found"
            self.guild_players[guild_id] = GuildPlayer(self, guild)
        return self.guild_players[guild_id]

    async def setup_hook(self) -> None:
        if config.SPOTIFY_ENABLED:
            self.spotify = SpotifyResolver(
                config.SPOTIFY_CLIENT_ID,
                config.SPOTIFY_CLIENT_SECRET,
            )
            log.info("Spotify resolver initialised.")
        else:
            log.warning("Spotify disabled (credentials not set).")

        for cog in COGS:
            await self.load_extension(cog)
            log.info("Loaded cog: %s", cog)

        log.info("Syncing slash commands globally ...")
        await self.tree.sync()

    async def on_ready(self) -> None:
        assert self.user
        log.info("Logged in as %s (id=%d)", self.user, self.user.id)
        await self.change_presence(activity=discord.Activity(
            type=discord.ActivityType.listening,
            name="/play",
        ))

    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ) -> None:
        if member.id != self.user.id:
            return
        if before.channel is not None and after.channel is None:
            player = self.guild_players.get(member.guild.id)
            if player:
                player.on_voice_disconnect()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    config.validate()
    bot = MusicBot()
    bot.run(config.DISCORD_TOKEN)


if __name__ == "__main__":
    main()
