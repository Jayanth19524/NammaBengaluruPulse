from enum import Enum
from typing import List
from datetime import datetime
from pydantic import BaseModel, Field, field_validator


class Severity(str, Enum):
    info = "info"
    low = "low"
    moderate = "moderate"
    high = "high"
    critical = "critical"


class VerificationStatus(str, Enum):
    confirmed = "confirmed"
    reported = "reported"
    predicted = "predicted"


class AgentName(str, Enum):
    FloodLens = "FloodLens"
    RoadTrust = "RoadTrust"
    WaterWatch = "WaterWatch"


class WaterIncidentType(str, Enum):
    supply_disruption = "supply_disruption"
    tanker_shortage = "tanker_shortage"
    sensor_anomaly = "sensor_anomaly"
    demand_spike = "demand_spike"


class Location(BaseModel):
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)


class AgentContract(BaseModel):
    agent: AgentName
    incident_type: str
    location: Location
    severity: Severity
    confidence: float = Field(..., ge=0.0, le=1.0)
    verification_status: VerificationStatus
    affected_route: bool
    evidence: List[str]
    source: List[str]
    recommended_action: str
    observed_at: datetime
    is_simulated: bool

    @field_validator("recommended_action")
    @classmethod
    def action_must_not_be_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("recommended_action must not be empty")
        return v

    @field_validator("incident_type")
    @classmethod
    def incident_type_must_not_be_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("incident_type must not be empty")
        return v
