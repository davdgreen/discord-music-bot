from __future__ import annotations
import discord
from discord import app_commands
from discord.ext import commands


class AdminCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="sync", description="[Owner] Sync slash commands to this guild instantly.")
    @app_commands.default_permissions(administrator=True)
    async def sync(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.bot.owner_id:
            await interaction.response.send_message("Owner-only command.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        assert interaction.guild
        self.bot.tree.copy_global_to(guild=interaction.guild)
        synced = await self.bot.tree.sync(guild=interaction.guild)
        await interaction.followup.send(
            f"Synced {len(synced)} command(s) to **{interaction.guild.name}**.",
            ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AdminCog(bot))
