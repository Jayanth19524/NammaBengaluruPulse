"""City configuration. Nothing city-specific is hardcoded in the agent."""
from __future__ import annotations

import json
import os
from pathlib import Path

from pydantic import BaseModel

DEFAULT_DIR = Path(__file__).resolve().parents[3] / "packages" / "city-config"


class RoadTrustSettings(BaseModel):
    default_corridor_m: float = 50
    dedup_radius_m: float = 25
    stale_after_days: int = 30
    min_detection_confidence: float = 0.4
    max_image_bytes: int = 8 * 1024 * 1024


class CityConfig(BaseModel):
    id: str
    name: str
    country: str
    bbox: tuple[float, float, float, float]  # min_lon, min_lat, max_lon, max_lat
    roadtrust: RoadTrustSettings = RoadTrustSettings()

    def contains(self, lat: float, lon: float) -> bool:
        min_lon, min_lat, max_lon, max_lat = self.bbox
        return min_lon <= lon <= max_lon and min_lat <= lat <= max_lat


def load_city(city_id: str | None = None, directory: Path | None = None) -> CityConfig:
    city_id = city_id or os.environ.get("NAMMAPULSE_CITY", "bengaluru")
    path = (directory or Path(os.environ.get("NAMMAPULSE_CITY_DIR", DEFAULT_DIR))) / f"{city_id}.json"
    return CityConfig.model_validate(json.loads(path.read_text()))
