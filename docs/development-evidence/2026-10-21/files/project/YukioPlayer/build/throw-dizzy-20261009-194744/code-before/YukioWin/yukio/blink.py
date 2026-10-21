"""Independent deterministic eyelid timing shared with the macOS player.

The clock intentionally survives activity changes. Selecting a state's seed
only affects future scheduling; a pending or active blink is never restarted.
"""

from __future__ import annotations


class BlinkClock:
    __slots__ = ("seed", "next_start", "duration", "_random_state", "_second")

    def __init__(self, seed: int, now: float):
        self.seed = int(seed) & 0xFFFFFFFF
        self._random_state = self.seed
        self.next_start = float(now)
        self.duration = 220.0
        self._second = None
        self._schedule(float(now))

    def select_seed(self, value: int) -> None:
        value = int(value) & 0xFFFFFFFF
        if self.seed == value:
            return
        self.seed = value
        self._random_state = value
        # next_start, duration and a pending second blink deliberately survive.

    def _random(self, low: float, high: float) -> float:
        self._random_state = (1664525 * self._random_state + 1013904223) & 0xFFFFFFFF
        return low + (high - low) * self._random_state / 4294967296.0

    def _schedule(self, end: float) -> None:
        self.next_start = end + self._random(2800.0, 7000.0)
        self.duration = self._random(180.0, 260.0)
        self._second = None
        if self._random(0.0, 1.0) < 0.125:
            start = self.next_start + self.duration + self._random(100.0, 180.0)
            self._second = (start, self._random(180.0, 260.0))

    def level(self, now: float, levels: int = 6) -> int:
        skipped = 0
        while now >= self.next_start + self.duration:
            if self._second is not None:
                self.next_start, self.duration = self._second
                self._second = None
            else:
                self._schedule(self.next_start + self.duration)
            skipped += 1
            # A very long sleep may discard invisible historical events.
            if skipped > 10000:
                self._schedule(float(now))
                break
        u = (now - self.next_start) / self.duration
        if not 0.0 < u < 1.0:
            return 0

        def smooth(value: float) -> float:
            value = min(max(value, 0.0), 1.0)
            return value * value * (3.0 - 2.0 * value)

        if u < 0.36:
            amount = smooth(u / 0.36)
        elif u < 0.52:
            amount = 1.0
        else:
            amount = 1.0 - smooth((u - 0.52) / 0.48)
        # Python's round uses bankers' rounding while Swift rounds halves away
        # from zero. The amount is non-negative, so +0.5 then floor matches it.
        return int(amount * int(levels) + 0.5)
