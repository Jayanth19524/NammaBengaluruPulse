"""Agent response contract (proposal for the Phase 0 freeze).

Mirrors packages/contracts/agent-response.schema.json. `distance_m` and
`route_id` are optional additions so the notification engine can show
"distance from your route" without recomputing geometry.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class Location(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class AgentResponse(BaseModel):
    agent: Literal["FloodLens", "RoadTrust", "WaterWatch"]
    incident_id: str
    incident_type: str
    location: Location
    severity: Literal["info", "low", "moderate", "high", "critical"]
    confidence: float = Field(ge=0, le=1)
    verification_status: Literal["confirmed", "reported", "predicted"]
    affected_route: bool
    route_id: str | None = None
    distance_m: float | None = Field(default=None, ge=0)
    evidence: list[dict] = []
    source: list[str] = []
    recommended_action: str
    observed_at: datetime
    is_simulated: bool = False
