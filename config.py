from __future__ import annotations
import shutil
import sys
from dotenv import load_dotenv
import os

load_dotenv()


def _require(key: str) -> str:
    val = os.getenv(key)
    if not val:
        print(f"ERROR: Missing required environment variable: {key}", file=sys.stderr)
        sys.exit(1)
    return val


DISCORD_TOKEN: str = _require("DISCORD_TOKEN")
SPOTIFY_CLIENT_ID: str = os.getenv("SPOTIFY_CLIENT_ID", "")
SPOTIFY_CLIENT_SECRET: str = os.getenv("SPOTIFY_CLIENT_SECRET", "")

SPOTIFY_ENABLED: bool = bool(SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET)


def validate() -> None:
    """Called at startup to catch obvious mis-configurations early."""
    if shutil.which("ffmpeg") is None:
        print("ERROR: ffmpeg not found on PATH. Install it with: sudo apt install -y ffmpeg", file=sys.stderr)
        sys.exit(1)
    if not SPOTIFY_ENABLED:
        print(
            "WARNING: SPOTIFY_CLIENT_ID / SPOTIFY_CLIENT_SECRET not set. "
            "Spotify URLs will be rejected.",
        )
