from __future__ import annotations
import discord
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.track import Track
    from core.queue import TrackQueue

COLOUR_OK = discord.Colour.blurple()
COLOUR_ERR = discord.Colour.red()
COLOUR_WARN = discord.Colour.yellow()

PAGE_SIZE = 10


def now_playing_embed(track: "Track", queue: "TrackQueue") -> discord.Embed:
    embed = discord.Embed(
        title="Now Playing",
        description=f"[{track.title}]({track.webpage_url})",
        colour=COLOUR_OK,
    )
    if track.thumbnail:
        embed.set_thumbnail(url=track.thumbnail)
    if track.uploader:
        embed.set_footer(text=f"Uploaded by {track.uploader}")
    embed.add_field(name="Duration", value=track.display_duration, inline=True)
    embed.add_field(name="Repeat", value=queue.repeat.value, inline=True)
    nxt = queue.peek_next()
    if nxt:
        embed.add_field(name="Up Next", value=nxt.title, inline=False)
    return embed


def queue_embed(queue: "TrackQueue", page: int = 1) -> discord.Embed:
    items = queue.items()
    total = len(items)
    max_page = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(1, min(page, max_page))

    start = (page - 1) * PAGE_SIZE
    end = start + PAGE_SIZE
    slice_ = items[start:end]

    lines: list[str] = []
    if queue.current:
        lines.append(f"**Now Playing:** {queue.current.title} `[{queue.current.display_duration}]`\n")

    for i, track in enumerate(slice_, start=start + 1):
        lines.append(f"`{i}.` {track.title} `[{track.display_duration}]`")

    if not lines:
        desc = "*The queue is empty.*"
    else:
        desc = "\n".join(lines)

    embed = discord.Embed(
        title=f"Queue - Page {page}/{max_page} ({total} track{'s' if total != 1 else ''})",
        description=desc,
        colour=COLOUR_OK,
    )
    embed.set_footer(text=f"Repeat: {queue.repeat.value}")
    return embed


def history_embed(tracks: list["Track"]) -> discord.Embed:
    if not tracks:
        desc = "*No history yet.*"
    else:
        lines = [
            f"`{i}.` {t.title} `[{t.display_duration}]`"
            for i, t in enumerate(reversed(tracks), 1)
        ]
        desc = "\n".join(lines)
    return discord.Embed(title="Recently Played", description=desc, colour=COLOUR_OK)


def error_embed(message: str) -> discord.Embed:
    return discord.Embed(description=f":x: {message}", colour=COLOUR_ERR)


def success_embed(message: str) -> discord.Embed:
    return discord.Embed(description=f":white_check_mark: {message}", colour=COLOUR_OK)


def export_text(queue: "TrackQueue") -> str:
    items = queue.items()
    if not items:
        return "Queue is empty."
    lines = [f"{i}. {t.title}" for i, t in enumerate(items, 1)]
    if queue.current:
        lines.insert(0, f"0. [NOW] {queue.current.title}")
    return "\n".join(lines)
