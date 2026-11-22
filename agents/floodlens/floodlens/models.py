from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class Route(BaseModel):
    id: str
    name: str = ""
    geometry: list[tuple[float, float]]  # (lon, lat)
    corridor_m: float | None = None


class Scenario(BaseModel):
    """A what-if rainfall, clearly not a forecast. Output built from it is flagged simulated."""
    accum_6h_mm: float
    peak_mm_h: float
    label: str = "What-if heavy rain"


class RainStats(BaseModel):
    lat: float
    lon: float
    peak_mm_h: float
    accum_6h_mm: float          # worst rolling 6-hour total in the window
    accum_24h_mm: float
    peak_at: datetime | None = None
    window_start: datetime | None = None   # first hour at or above 5 mm/h
    window_end: datetime | None = None
    hours: int = 0


class Cell(BaseModel):
    id: str
    lat: float
    lon: float
    elevation_m: float
    relief_m: float            # >0: lower than the surroundings (water collects), <0: higher
    depression: float = 0.0    # 0..1
    rain_score: float = 0.0    # 0..1
    risk: float = 0.0          # 0..1 model estimate
    severity: str = "info"
    reported: bool = False


class Cluster(BaseModel):
    id: str
    route_id: str
    lat: float
    lon: float
    risk: float
    severity: str
    distance_m: float
    relief_m: float
    elevation_m: float
    n_cells: int
    reported: bool


class Report(BaseModel):
    id: str
    lat: float
    lon: float
    at: datetime
    depth_cm: float | None = None
    note: str = ""
    reporter_hash: str
