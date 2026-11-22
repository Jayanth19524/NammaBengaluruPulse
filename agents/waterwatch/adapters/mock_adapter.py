"""
Mock adapter — always available, returns realistic simulated incidents.
Every result has is_simulated=True. Used when USE_MOCK_ADAPTER=true or as fallback.
"""
import math
from typing import List
from .base import WaterAdapter, RawWaterData

# Fixed demo incidents anchored to Bengaluru neighbourhoods
_DEMO_INCIDENTS = [
    RawWaterData(
        incident_type="supply_disruption",
        latitude=12.9299, longitude=77.5832,
        duration_hrs=18.0, report_count=12, area_km2=0.8,
        sensor_deviation=0.0,
        evidence=["12 community reports in last 2 hrs", "BWSSB maintenance notice #2024-1182"],
        source=["mock_adapter"],
        area_name="Jayanagar",
        is_simulated=True,
    ),
    RawWaterData(
        incident_type="tanker_shortage",
        latitude=12.9352, longitude=77.6232,
        duration_hrs=4.0, report_count=5, area_km2=0.3,
        sensor_deviation=0.0,
        evidence=["Tanker operator reports 4-hr delay", "5 residents reported no tanker arrival"],
        source=["mock_adapter"],
        area_name="Koramangala",
        is_simulated=True,
    ),
    RawWaterData(
        incident_type="sensor_anomaly",
        latitude=12.9784, longitude=77.6408,
        duration_hrs=0.5, report_count=0, area_km2=0.1,
        sensor_deviation=0.67,
        evidence=["Pressure sensor ESP32-IND-001 reading 0.4 bar (normal: 1.2 bar)", "Flow rate down 60%"],
        source=["mock_adapter"],
        area_name="Indiranagar",
        is_simulated=True,
    ),
    RawWaterData(
        incident_type="demand_spike",
        latitude=12.9698, longitude=77.7480,
        duration_hrs=3.0, report_count=0, area_km2=1.5,
        sensor_deviation=0.0,
        evidence=["Demand 40% above daily average", "Industrial usage spike detected"],
        source=["mock_adapter"],
        area_name="Whitefield",
        is_simulated=True,
    ),
    RawWaterData(
        incident_type="supply_disruption",
        latitude=12.9081, longitude=77.6414,
        duration_hrs=36.0, report_count=23, area_km2=1.2,
        sensor_deviation=0.0,
        evidence=["BWSSB confirmed main pipe burst on 27th Main", "Repair crew dispatched at 06:00 AM"],
        source=["mock_adapter"],
        area_name="HSR Layout",
        is_simulated=True,
    ),
]


def _haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Return distance in metres between two lat/lng points."""
    R = 6_371_000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


class MockAdapter(WaterAdapter):
    @property
    def name(self) -> str:
        return "mock_adapter"

    async def fetch(self, lat: float, lng: float, radius_m: float) -> List[RawWaterData]:
        return [
            inc for inc in _DEMO_INCIDENTS
            if _haversine_m(lat, lng, inc.latitude, inc.longitude) <= radius_m
        ]
