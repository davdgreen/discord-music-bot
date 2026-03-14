# Discord Music Bot

A self-hosted Discord music bot modeled after FredBoat. Streams audio from YouTube via yt-dlp + FFmpeg, resolves Spotify URLs by searching YouTube, and exposes everything through slash commands.

## Features

- Stream audio from YouTube URLs, search queries, or Spotify track/album/playlist URLs
- Full queue management: add, remove, move, clear, shuffle, export
- Seek, forward, rewind, restart
- Repeat modes: off / one / all
- Playback history
- Auto-disconnect after 5 minutes of inactivity
- Now-playing embed that updates as tracks change

## Requirements

- Python 3.12+
- FFmpeg installed on system PATH
- Discord bot token
- Spotify API credentials (optional — only needed for Spotify URL support)

## Setup

### 1. Create the Discord Bot

1. Go to [discord.com/developers/applications](https://discord.com/developers/applications) → **New Application**
2. Left sidebar → **Bot** → **Reset Token** → copy the token
3. Enable **Server Members Intent** and **Message Content Intent** under Privileged Gateway Intents
4. Left sidebar → **OAuth2 → URL Generator**
   - Scopes: `bot`, `applications.commands`
   - Permissions: `Connect`, `Speak`, `Send Messages`, `Embed Links`, `Attach Files`, `Read Message History`
5. Open the generated URL → invite the bot to your server

### 2. Create a Spotify App (optional)

1. Go to [developer.spotify.com/dashboard](https://developer.spotify.com/dashboard) → **Create App**
2. Settings → copy **Client ID** and **Client Secret**

### 3. Install FFmpeg

**Ubuntu / WSL2:**
```bash
sudo apt update && sudo apt install -y ffmpeg
```

**macOS:**
```bash
brew install ffmpeg
```

### 4. Install Python Dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 5. Configure Environment

```bash
cp .env.example .env
```

Edit `.env`:
```
DISCORD_TOKEN=your_bot_token_here
SPOTIFY_CLIENT_ID=your_spotify_client_id_here
SPOTIFY_CLIENT_SECRET=your_spotify_client_secret_here
```

Spotify credentials are optional. Leave them blank to disable Spotify support.

### 6. Run

```bash
python bot.py
```

Slash commands sync globally on startup and can take up to 1 hour to appear in Discord. For instant sync to a specific server, run `/sync` in any channel the bot can see (owner only).

## Commands

| Command | Args | Description |
|---|---|---|
| `/play` | `query` | YouTube URL, search string, or Spotify URL |
| `/pause` | — | Pause playback |
| `/resume` | — | Resume playback |
| `/stop` | — | Stop and clear queue |
| `/skip` | — | Skip current track |
| `/nowplaying` | — | Show current track embed |
| `/seek` | `timestamp` | Jump to position (`1:30` or `90`) |
| `/forward` | `seconds=10` | Seek forward N seconds |
| `/rewind` | `seconds=10` | Seek back N seconds |
| `/restart` | — | Restart current track from beginning |
| `/queue` | `page=1` | Show paginated queue |
| `/remove` | `index` | Remove track at 1-based index |
| `/clear` | — | Clear entire queue |
| `/move` | `from`, `to` | Reposition track in queue |
| `/repeat` | `mode` | `off` / `one` / `all` |
| `/shuffle` | — | Shuffle queue |
| `/reshuffle` | — | Re-randomize queue |
| `/history` | `count=10` | Recently played tracks |
| `/export` | — | Download queue as a text file |
| `/join` | — | Join your voice channel |
| `/leave` | — | Disconnect |
| `/sync` | — | (Owner) Instantly sync slash commands to this server |

## Project Structure

```
music-bot/
├── bot.py                # Entry point: MusicBot subclass, cog loader, event handlers
├── config.py             # .env loader with startup validation
├── requirements.txt
├── .env.example
│
├── cogs/
│   ├── music.py          # All slash command definitions
│   └── admin.py          # /sync command (owner-only)
│
├── core/
│   ├── player.py         # GuildPlayer: voice client, queue driver, seek, inactivity watchdog
│   ├── queue.py          # TrackQueue: deque + repeat/shuffle logic
│   ├── track.py          # Track dataclass with seek_offset support
│   ├── audio_source.py   # FFmpegYTDLSource: yt-dlp resolver + FFmpegOpusAudio
│   └── spotify.py        # SpotifyResolver: Spotify URL -> Track stubs
│
└── utils/
    ├── embeds.py          # Embed factory functions
    ├── time_fmt.py        # seconds_to_hms / hms_to_seconds
    └── checks.py          # ensure_in_voice / ensure_same_voice helpers
```

## How It Works

**Audio pipeline:**
1. `/play` defers the interaction, resolves Spotify URLs if needed, then enqueues a `Track`
2. `GuildPlayer.play_next()` calls `FFmpegYTDLSource.create()` which runs yt-dlp in a thread executor to get a direct stream URL
3. `discord.FFmpegOpusAudio` streams the audio with `-reconnect` flags to handle drops on long tracks
4. When a track ends, `_after_play` schedules `play_next()` via `run_coroutine_threadsafe`

**Seek:**
Seeking pushes a copy of the current track with a new `seek_offset` to the front of the queue, then stops playback. The `after` callback picks up the seeked copy and restarts with `-ss <offset>` passed to FFmpeg.

**Spotify:**
Spotify URLs are resolved to `Track` stubs using Client Credentials (no user login). Each stub's `webpage_url` is a `ytsearch:` query that yt-dlp resolves lazily at play time, so large playlists enqueue instantly.

## Keeping the Bot Running

```bash
# Run detached, log to file
nohup python bot.py > bot.log 2>&1 &

# Follow logs
tail -f bot.log

# Stop
kill $(pgrep -f "python bot.py")
```

Or use `screen` or `tmux` for an interactive detachable session.
