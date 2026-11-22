from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

Severity = Literal["info", "low", "moderate", "high", "critical"]
SEV_ORDER = ["info", "low", "moderate", "high", "critical"]


class MonitoredRoute(BaseModel):
    id: str
    name: str = ""
    origin: tuple[float, float]       # lat, lon
    destination: tuple[float, float]
    geometry: list[tuple[float, float]] | None = None  # (lon, lat); used if routing is unavailable
    corridor_m: float | None = None
    categories: list[Literal["road", "traffic"]] = ["road", "traffic"]
    min_severity: Severity = "low"


class Finding(BaseModel):
    key: str                      # stable identity, used for dedup and cooldown
    agent: Literal["RoadTrust", "TripCast"]
    category: Literal["road", "traffic"]
    kind: str
    title: str
    lat: float | None = None
    lon: float | None = None
    severity: Severity
    basis: Literal["confirmed", "reported", "predicted"]
    confidence: float = Field(ge=0, le=1)
    route_ids: list[str]
    distance_m: float | None = None
    corridor_m: float | None = None
    evidence: list[dict] = []
    sources: list[str] = []
    action: str
    observed_at: datetime
    simulated: bool = False
    incident_id: str | None = None
    score: float | None = None
    score_parts: dict[str, float] = {}


class Decision(BaseModel):
    key: str
    action: Literal["alert", "suppress"]
    rank: int | None = None
    reasons: list[str]
    finding: Finding


class RunRequest(BaseModel):
    routes: list[MonitoredRoute]
    include_simulated: bool = False
    depart_at: datetime | None = None
