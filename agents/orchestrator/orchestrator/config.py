from __future__ import annotations

import json
import os
from pathlib import Path

from pydantic import BaseModel

DEFAULT_DIR = Path(__file__).resolve().parents[3] / "packages" / "city-config"


class TrafficRules(BaseModel):
    min_surprise_s: float = 300          # predicted minus departure-time estimate
    min_surprise_ratio: float = 0.15
    severe_ratio: float = 1.8            # predicted / free-flow
    severity_by_ratio: list[tuple[float, str]] = [(2.2, "high"), (1.8, "moderate"), (1.4, "low")]
    min_alt_saving_s: float = 180


class Settings(BaseModel):
    relevance_threshold: float = 0.45
    weights: dict[str, float] = {"severity": 0.40, "proximity": 0.25, "basis": 0.20, "confidence": 0.15}
    severity_weight: dict[str, float] = {"info": 0.1, "low": 0.35, "moderate": 0.6, "high": 0.85, "critical": 1.0}
    basis_weight: dict[str, float] = {"confirmed": 1.0, "reported": 0.7, "predicted": 0.6}
    cooldown_hours: float = 6
    max_alerts_per_run: int = 5
    traffic: TrafficRules = TrafficRules()


def load_settings(city: str | None = None, directory: Path | None = None) -> Settings:
    city = city or os.environ.get("NAMMAPULSE_CITY", "bengaluru")
    path = (directory or Path(os.environ.get("NAMMAPULSE_CITY_DIR", DEFAULT_DIR))) / f"{city}.json"
    return Settings.model_validate(json.loads(path.read_text()).get("orchestrator", {}))
