from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List


@dataclass
class RawWaterData:
    """Raw data returned from any water adapter before scoring."""
    incident_type: str              # supply_disruption | tanker_shortage | sensor_anomaly | demand_spike
    latitude: float
    longitude: float
    duration_hrs: float             # how long the issue has lasted / is expected to last
    report_count: int               # number of community reports corroborating the incident
    area_km2: float                 # affected area estimate
    sensor_deviation: float         # 0.0 = normal, 1.0 = fully deviated (use 0.0 for non-sensor types)
    evidence: List[str] = field(default_factory=list)
    source: List[str] = field(default_factory=list)
    area_name: str = ""
    is_simulated: bool = False


class WaterAdapter(ABC):
    """Abstract base class every water data adapter must implement."""

    @abstractmethod
    async def fetch(
        self, lat: float, lng: float, radius_m: float
    ) -> List[RawWaterData]:
        """Fetch raw water incident data for the given location and radius."""
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable adapter name used in source[] field."""
        ...
