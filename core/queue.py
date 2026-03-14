from __future__ import annotations
import random
from collections import deque
from enum import Enum
from typing import Optional

from core.track import Track


class RepeatMode(Enum):
    OFF = "off"
    ONE = "one"
    ALL = "all"


class TrackQueue:
    def __init__(self) -> None:
        self._queue: deque[Track] = deque()
        self._history: deque[Track] = deque(maxlen=50)
        self.repeat: RepeatMode = RepeatMode.OFF
        self.current: Optional[Track] = None

    def add(self, track: Track) -> None:
        self._queue.append(track)

    def add_front(self, track: Track) -> None:
        self._queue.appendleft(track)

    def clear(self) -> None:
        self._queue.clear()

    def shuffle(self) -> None:
        items = list(self._queue)
        random.shuffle(items)
        self._queue = deque(items)

    def remove(self, index: int) -> Track:
        items = list(self._queue)
        if not (1 <= index <= len(items)):
            raise IndexError(f"Index {index} out of range (queue has {len(items)} items)")
        removed = items.pop(index - 1)
        self._queue = deque(items)
        return removed

    def move(self, from_index: int, to_index: int) -> None:
        items = list(self._queue)
        n = len(items)
        if not (1 <= from_index <= n) or not (1 <= to_index <= n):
            raise IndexError("Index out of range")
        track = items.pop(from_index - 1)
        items.insert(to_index - 1, track)
        self._queue = deque(items)

    def pop_next(self) -> Optional[Track]:
        if self.repeat == RepeatMode.ONE and self.current is not None:
            return self.current.with_seek(0)

        if not self._queue:
            if self.repeat == RepeatMode.ALL and self.current is not None:
                self.current = self.current.with_seek(0)
                return self.current
            self.current = None
            return None

        track = self._queue.popleft()

        if self.repeat == RepeatMode.ALL and self.current is not None:
            self._queue.append(self.current.with_seek(0))

        if self.current is not None:
            self._history.append(self.current)

        self.current = track
        return track

    def peek_next(self) -> Optional[Track]:
        return self._queue[0] if self._queue else None

    def __len__(self) -> int:
        return len(self._queue)

    def is_empty(self) -> bool:
        return len(self._queue) == 0

    def items(self) -> list[Track]:
        return list(self._queue)

    def history(self, count: int = 10) -> list[Track]:
        return list(self._history)[-count:]
