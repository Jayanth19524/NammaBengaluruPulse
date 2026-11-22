"""Time-dependent travel time.

Why not just use the time shown at departure? Traffic changes while you drive. A trip
that starts at 07:40 with light traffic reaches its later segments at 08:10, when the
peak has built. So each step is costed at the moment you will actually reach it.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Protocol

from .models import CandidateRoute, Prediction
from .profile import CongestionProfile


class LiveTraffic(Protocol):
    name: str

    def ratio_at(self, lon: float, lat: float) -> float | None:
        """Current travel time / free-flow time near this point, or None if unknown."""


class Predictor:
    def __init__(self, profile: CongestionProfile, live: LiveTraffic | None = None,
                 live_horizon_min: float = 45, uncertainty: float = 0.12):
        self.profile, self.live = profile, live
        self.horizon = live_horizon_min * 60
        self.u = uncertainty

    def _live_scale(self, route: CandidateRoute, now: datetime) -> list[float]:
        """Per-step ratio of live conditions to what the profile expects right now.
        Today's deviation (an accident, rain) decays back to the profile over the horizon."""
        if self.live is None:
            return [1.0] * len(route.steps)
        expected_now = self.profile.multiplier(now)
        out, last = [], 1.0
        for s in route.steps:
            r = self.live.ratio_at(*s.mid) if s.mid else None
            last = (r / expected_now) if r else last
            out.append(last)
        return out

    def predict(self, route: CandidateRoute, depart: datetime, now: datetime | None = None) -> Prediction:
        now = now or depart
        scale = self._live_scale(route, now)
        t = depart
        for step, sc in zip(route.steps, scale):
            ahead = max(0.0, (t - now).total_seconds())
            w = max(0.0, 1 - ahead / self.horizon) if self.live else 0.0
            m = self.profile.multiplier(t) * (1 + w * (sc - 1))
            t = t + timedelta(seconds=step.free_flow_s * max(m, 1.0))
        total = (t - depart).total_seconds()
        snap_scale = scale[0] if self.live else 1.0
        snapshot = route.free_flow_s * max(self.profile.multiplier(depart) * snap_scale, 1.0)
        basis = ("assumed time-of-day profile" if self.profile.source == "assumed" else f"{self.profile.source} profile")
        if self.live:
            basis += f" adjusted with live traffic ({self.live.name})"
        return Prediction(predicted_s=round(total), low_s=round(total * (1 - self.u)), high_s=round(total * (1 + self.u)),
                          snapshot_s=round(snapshot), free_flow_s=round(route.free_flow_s), arrive_at=t, basis=basis)
