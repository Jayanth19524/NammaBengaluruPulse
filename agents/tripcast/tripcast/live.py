"""Optional live traffic from the TomTom Traffic Flow API (needs TOMTOM_API_KEY).
Without a key TripCast uses only the time-of-day profile and says so."""
from __future__ import annotations

import httpx

URL = "https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/10/json"


class TomTomLive:
    name = "TomTom"

    def __init__(self, key: str, client: httpx.Client | None = None, timeout: float = 5.0):
        self.key, self._client, self.timeout = key, client, timeout
        self._cache: dict[tuple[float, float], float | None] = {}

    def ratio_at(self, lon: float, lat: float) -> float | None:
        k = (round(lat, 3), round(lon, 3))  # ~100 m cells; keeps API calls down
        if k in self._cache:
            return self._cache[k]
        try:
            client = self._client or httpx.Client(timeout=self.timeout)
            r = client.get(URL, params={"point": f"{lat},{lon}", "key": self.key})
            r.raise_for_status()
            seg = r.json()["flowSegmentData"]
            ratio = seg["currentTravelTime"] / seg["freeFlowTravelTime"] if seg["freeFlowTravelTime"] else None
        except (httpx.HTTPError, KeyError, ValueError, ZeroDivisionError):
            ratio = None
        self._cache[k] = ratio
        return ratio
