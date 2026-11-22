"""Time-of-day congestion profile: multiplier = travel time / free-flow travel time.

IMPORTANT: the default values below are ASSUMPTIONS shaped like a typical large-city
weekday (morning and evening peaks). They are not measured Bengaluru data. Replace
them with values derived from real observations (e.g. a traffic-data export) and the
predictor will use those instead. Predictions are labelled accordingly.
"""
from __future__ import annotations

from datetime import datetime

WEEKDAY = [1.0, 1.0, 1.0, 1.0, 1.0, 1.05, 1.2, 1.5, 1.9, 2.0, 1.7, 1.4,
           1.35, 1.3, 1.3, 1.35, 1.5, 1.9, 2.2, 2.0, 1.6, 1.3, 1.1, 1.0]
WEEKEND = [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.05, 1.1, 1.2, 1.35, 1.45, 1.5,
           1.5, 1.45, 1.4, 1.4, 1.45, 1.55, 1.6, 1.5, 1.35, 1.2, 1.1, 1.0]


class CongestionProfile:
    def __init__(self, weekday: list[float] = WEEKDAY, weekend: list[float] = WEEKEND, source: str = "assumed"):
        if len(weekday) != 24 or len(weekend) != 24:
            raise ValueError("profiles need 24 hourly values")
        self.weekday, self.weekend, self.source = weekday, weekend, source

    def multiplier(self, t: datetime) -> float:
        """Linear interpolation between hourly values (hour value applies at the hour's start)."""
        table = self.weekend if t.weekday() >= 5 else self.weekday
        pos = t.hour + t.minute / 60 + t.second / 3600
        lo = int(pos) % 24
        hi = (lo + 1) % 24
        frac = pos - int(pos)
        return table[lo] * (1 - frac) + table[hi] * frac
