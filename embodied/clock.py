"""Time that can be handed in, so that what is timed can be tested without waiting for it."""

from __future__ import annotations

import threading
import time


class Clock:
    """The real clock."""

    def now(self) -> float:
        """Seconds, from a start that does not matter. It never runs backward."""
        return time.monotonic()

    def sleep(self, seconds: float) -> None:
        if seconds > 0:
            time.sleep(seconds)


class StepClock(Clock):
    """A clock that moves only when it is slept on: for tests, and safe from any thread."""

    def __init__(self, start: float = 0.0):
        self._t = start
        self._lock = threading.Lock()

    def now(self) -> float:
        with self._lock:
            return self._t

    def sleep(self, seconds: float) -> None:
        if seconds > 0:
            with self._lock:
                self._t += seconds
