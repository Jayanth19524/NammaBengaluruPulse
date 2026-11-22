from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

Severity = Literal["info", "low", "moderate", "high", "critical"]
SEVERITY_ORDER: list[Severity] = ["info", "low", "moderate", "high", "critical"]
Kind = Literal["pothole", "road_damage", "closure", "construction", "other"]
Verification = Literal["confirmed", "reported"]  # RoadTrust never emits "predicted"
RepairStatus = Literal["open", "repair_reported", "repaired"]


class Route(BaseModel):
    id: str
    name: str = ""
    geometry: list[tuple[float, float]]  # [(lon, lat), ...]
    corridor_m: float | None = None


class Detection(BaseModel):
    label: str
    confidence: float
    bbox: tuple[float, float, float, float]  # x1, y1, x2, y2 in pixels


class DetectionResult(BaseModel):
    available: bool  # False => no computer vision was run
    detections: list[Detection] = []
    image_width: int = 0
    image_height: int = 0
    note: str = ""


class RepairEvent(BaseModel):
    status: RepairStatus
    at: datetime
    source: str
    official: bool


class Incident(BaseModel):
    id: str
    kind: Kind
    latitude: float
    longitude: float
    severity: Severity
    verification_status: Verification = "reported"
    repair_status: RepairStatus = "open"
    first_seen: datetime
    last_seen: datetime
    reporter_ids: set[str] = set()  # hashed; never exposed in responses
    report_count: int = 1
    description: str = ""
    sources: list[str] = []
    evidence: list[dict] = []
    confidence: float = Field(default=0.5, ge=0, le=1)
    is_simulated: bool = False
    expires_at: datetime | None = None  # set by sources that publish an end date
    repair_history: list[RepairEvent] = []


class IncomingReport(BaseModel):
    """A user report or an adapter record before dedup."""
    kind: Kind = "pothole"
    latitude: float
    longitude: float
    severity: Severity = "low"
    description: str = ""
    reporter_id: str  # already hashed
    source: str
    observed_at: datetime
    confidence: float = 0.5
    evidence: list[dict] = []
    verification_status: Verification = "reported"
    is_simulated: bool = False
    expires_at: datetime | None = None
