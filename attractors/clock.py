"""Simulated clock. All sim-time policy lives in RunSpec; all jitter goes
through the per-run seeded rng so runs are reproducible."""

from __future__ import annotations

import random
from datetime import datetime, timedelta


class SimClock:
    def __init__(self, start: datetime, rng: random.Random):
        self._now = start
        self.start = start
        self.rng = rng

    @property
    def now(self) -> datetime:
        return self._now

    def advance(self, delta: timedelta) -> timedelta:
        if delta.total_seconds() < 0:
            raise ValueError("clock cannot go backwards")
        self._now += delta
        return delta

    def advance_to_next_morning(self, hour: int = 8) -> timedelta:
        target = self._now.replace(hour=hour, minute=0, second=0, microsecond=0)
        while target <= self._now:
            target += timedelta(days=1)
        return self.advance(target - self._now)

    def jitter(self, lo_s: float, hi_s: float) -> timedelta:
        return timedelta(seconds=self.rng.uniform(lo_s, hi_s))

    def stamp(self) -> str:
        return self._now.strftime("%Y-%m-%d %H:%M")

    def iso(self) -> str:
        return self._now.isoformat(timespec="seconds")

    @property
    def sim_date(self) -> str:
        return self._now.strftime("%Y-%m-%d")

    def elapsed_hours(self) -> float:
        return (self._now - self.start).total_seconds() / 3600.0
