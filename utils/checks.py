from __future__ import annotations
import discord
from discord import app_commands


class NotInVoice(app_commands.AppCommandError):
    pass


class NotSameVoice(app_commands.AppCommandError):
    pass


def ensure_in_voice(interaction: discord.Interaction) -> discord.VoiceChannel:
    member = interaction.user
    if not isinstance(member, discord.Member) or not member.voice or not member.voice.channel:
        raise NotInVoice("You must be in a voice channel to use this command.")
    vc = member.voice.channel
    if not isinstance(vc, discord.VoiceChannel):
        raise NotInVoice("Stage channels are not supported.")
    return vc


def ensure_same_voice(
    interaction: discord.Interaction,
    bot_vc: discord.VoiceClient | None,
) -> None:
    if bot_vc is None or not bot_vc.is_connected():
        return
    member = interaction.user
    if isinstance(member, discord.Member) and member.voice:
        if member.voice.channel != bot_vc.channel:
            raise NotSameVoice("You must be in the same voice channel as the bot.")
