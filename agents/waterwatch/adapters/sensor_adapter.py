"""
IoT/ESP32 sensor adapter — accepts telemetry payloads via HTTP POST.
When called in read-only fetch mode, returns latest simulated reading with is_simulated=True.
"""
from typing import List
from .base import WaterAdapter, RawWaterData


class SensorAdapter(WaterAdapter):
    @property
    def name(self) -> str:
        return "iot_sensor"

    async def fetch(self, lat: float, lng: float, radius_m: float) -> List[RawWaterData]:
        # In a real integration, query the sensor readings DB table for
        # devices within radius_m of lat/lng and compute deviation.
        # For now, return empty — the mock adapter covers demo sensor data.
        return []
