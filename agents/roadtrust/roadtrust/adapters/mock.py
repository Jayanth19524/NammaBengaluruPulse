"""Clearly labelled mock adapter for demos and offline work. Everything it emits
has is_simulated=True and a source ending in '(demo data)'."""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

from ..models import IncomingReport
from .base import BBox

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "mock_incidents.json"


class MockRoadAdapter:
    name = "RoadTrust mock feed (demo data)"
    is_simulated = True

    def __init__(self, fixture: Path = FIXTURE):
        self._rows = json.loads(fixture.read_text())

    def fetch(self, bbox: BBox, now: datetime) -> list[IncomingReport]:
        min_lon, min_lat, max_lon, max_lat = bbox
        out = []
        for row in self._rows:
            if not (min_lon <= row["longitude"] <= max_lon and min_lat <= row["latitude"] <= max_lat):
                continue
            out.append(IncomingReport(
                kind=row["kind"], latitude=row["latitude"], longitude=row["longitude"],
                severity=row["severity"], description=row["description"],
                reporter_id=f"mock:{row['id']}", source=self.name,
                observed_at=now - timedelta(hours=row.get("hours_ago", 1)),
                confidence=0.5, is_simulated=True,
            ))
        return out
