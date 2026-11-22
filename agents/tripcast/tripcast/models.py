from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class Step(BaseModel):
    free_flow_s: float
    distance_m: float
    name: str = ""
    # (lon, lat) at the step midpoint, used for live-traffic lookups
    mid: tuple[float, float] | None = None


class CandidateRoute(BaseModel):
    steps: list[Step]
    geometry: list[tuple[float, float]]  # [(lon, lat)]

    @property
    def free_flow_s(self) -> float:
        return sum(s.free_flow_s for s in self.steps)

    @property
    def distance_m(self) -> float:
        return sum(s.distance_m for s in self.steps)


class Prediction(BaseModel):
    predicted_s: float
    low_s: float
    high_s: float
    snapshot_s: float  # what a departure-time snapshot would show
    free_flow_s: float
    arrive_at: datetime
    basis: str  # human-readable description of the data behind the estimate


class PlannedRoute(BaseModel):
    id: str
    geometry: list[tuple[float, float]]
    distance_m: float
    prediction: Prediction
    via: list[str] = []
    warnings: list[dict] = []
    recommended: bool = False
    delta_vs_best_s: float = 0
    incidents_on_route: int = 0


class DepartureOption(BaseModel):
    depart_at: datetime
    predicted_s: float
    arrive_at: datetime


class PlanRequest(BaseModel):
    origin: tuple[float, float]  # lat, lon
    destination: tuple[float, float]
    depart_at: datetime | None = None
    check_incidents: bool = True
