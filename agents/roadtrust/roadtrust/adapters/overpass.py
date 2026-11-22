"""OpenStreetMap road closures and construction via the Overpass API.
OSM is community-maintained, so these are 'reported', not 'confirmed'."""
from __future__ import annotations

from datetime import datetime

import httpx

from ..models import IncomingReport
from .base import AdapterError, BBox

URL = "https://overpass-api.de/api/interpreter"


class OverpassAdapter:
    name = "OpenStreetMap (Overpass)"
    is_simulated = False

    def __init__(self, url: str = URL, timeout: float = 15.0, client: httpx.Client | None = None):
        self.url, self.timeout, self._client = url, timeout, client

    @staticmethod
    def build_query(bbox: BBox) -> str:
        w, s, e, n = bbox
        b = f"{s},{w},{n},{e}"
        return (f'[out:json][timeout:15];(way["highway"="construction"]({b});'
                f'way["access"="no"]["highway"]({b}););out center tags;')

    def fetch(self, bbox: BBox, now: datetime) -> list[IncomingReport]:
        try:
            client = self._client or httpx.Client(timeout=self.timeout)
            resp = client.post(self.url, data={"data": self.build_query(bbox)})
            resp.raise_for_status()
            elements = resp.json().get("elements", [])
        except (httpx.HTTPError, ValueError) as exc:
            raise AdapterError(f"Overpass unavailable: {exc}") from exc
        out = []
        for el in elements:
            c = el.get("center")
            if not c:
                continue
            tags = el.get("tags", {})
            construction = tags.get("highway") == "construction"
            out.append(IncomingReport(
                kind="construction" if construction else "closure",
                latitude=c["lat"], longitude=c["lon"], severity="moderate",
                description=tags.get("name", "Road works" if construction else "Access restricted"),
                reporter_id=f"osm:way/{el['id']}", source=self.name, observed_at=now, confidence=0.6,
                evidence=[{"type": "osm_way", "id": el["id"], "tags": tags}],
            ))
        return out
