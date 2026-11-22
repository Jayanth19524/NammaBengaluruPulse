from __future__ import annotations

from datetime import datetime
from typing import Protocol

from ..models import IncomingReport

BBox = tuple[float, float, float, float]  # min_lon, min_lat, max_lon, max_lat


class AdapterError(Exception):
    pass


class RoadAdapter(Protocol):
    name: str
    is_simulated: bool

    def fetch(self, bbox: BBox, now: datetime) -> list[IncomingReport]: ...
