from __future__ import annotations
from dataclasses import dataclass
from typing import Optional


@dataclass
class Track:
    title: str
    webpage_url: str
    duration: Optional[int] = None
    thumbnail: Optional[str] = None
    uploader: Optional[str] = None
    seek_offset: int = 0

    def with_seek(self, seconds: int) -> Track:
        return Track(
            title=self.title,
            webpage_url=self.webpage_url,
            duration=self.duration,
            thumbnail=self.thumbnail,
            uploader=self.uploader,
            seek_offset=seconds,
        )

    @property
    def display_duration(self) -> str:
        from utils.time_fmt import seconds_to_hms
        if self.duration is None:
            return "Live"
        return seconds_to_hms(self.duration)

    def __str__(self) -> str:
        return f"{self.title} [{self.display_duration}]"
