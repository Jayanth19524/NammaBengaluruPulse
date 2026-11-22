"""Real data sources (Open-Meteo, free, no key). Each is an interface so tests and fallbacks can swap them."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Protocol

import httpx

from .models import RainStats

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
ELEVATION_URL = "https://api.open-meteo.com/v1/elevation"


class SourceError(Exception):
    pass


class ElevationSource(Protocol):
    name: str

    def elevations(self, pts: list[tuple[float, float]]) -> list[float]: ...


class RainSource(Protocol):
    name: str

    def forecast(self, pts: list[tuple[float, float]]) -> list[RainStats]: ...


def _get(client, url, params, timeout):
    try:
        c = client or httpx.Client(timeout=timeout)
        r = c.get(url, params=params)
        r.raise_for_status()
        return r.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise SourceError(str(exc)) from exc


class OpenMeteoElevation:
    name = "Open-Meteo elevation (Copernicus DEM, ~90 m)"

    def __init__(self, client: httpx.Client | None = None, timeout: float = 20.0):
        self._client, self.timeout = client, timeout
        self._cache: dict[tuple[float, float], float] = {}

    def elevations(self, pts):
        todo = [p for p in pts if p not in self._cache]
        for i in range(0, len(todo), 100):  # API limit: 100 coordinates per request
            chunk = todo[i:i + 100]
            data = _get(self._client, ELEVATION_URL, {"latitude": ",".join(str(p[0]) for p in chunk),
                                                      "longitude": ",".join(str(p[1]) for p in chunk)}, self.timeout)
            vals = data.get("elevation")
            if not vals or len(vals) != len(chunk):
                raise SourceError("unexpected elevation response")
            self._cache.update(zip(chunk, (float(v) for v in vals)))
        return [self._cache[p] for p in pts]


def rain_stats(lat: float, lon: float, times: list[datetime], mm: list[float]) -> RainStats:
    mm = [v or 0.0 for v in mm]
    n = len(mm)
    accum6 = max((sum(mm[i:i + 6]) for i in range(max(1, n - 5))), default=0.0)
    peak = max(mm, default=0.0)
    peak_at = times[mm.index(peak)] if mm and peak > 0 else None
    heavy = [t for t, v in zip(times, mm) if v >= 5]
    return RainStats(lat=lat, lon=lon, peak_mm_h=round(peak, 1), accum_6h_mm=round(accum6, 1),
                     accum_24h_mm=round(sum(mm[:24]), 1), peak_at=peak_at,
                     window_start=heavy[0] if heavy else None, window_end=(heavy[-1] + timedelta(hours=1)) if heavy else None,
                     hours=n)


class OpenMeteoRain:
    name = "Open-Meteo weather forecast"

    def __init__(self, client: httpx.Client | None = None, timeout: float = 20.0, days: int = 2):
        self._client, self.timeout, self.days = client, timeout, days

    def forecast(self, pts):
        data = _get(self._client, FORECAST_URL, {
            "latitude": ",".join(str(p[0]) for p in pts), "longitude": ",".join(str(p[1]) for p in pts),
            "hourly": "precipitation", "forecast_days": self.days, "timezone": "UTC"}, self.timeout)
        items = data if isinstance(data, list) else [data]
        if len(items) != len(pts):
            raise SourceError("unexpected forecast response")
        out = []
        for (lat, lon), d in zip(pts, items):
            try:
                times = [datetime.fromisoformat(t).replace(tzinfo=timezone.utc) for t in d["hourly"]["time"]]
                out.append(rain_stats(lat, lon, times, d["hourly"]["precipitation"]))
            except (KeyError, ValueError) as exc:
                raise SourceError(f"bad forecast payload: {exc}") from exc
        return out
