"""Model settings. THESE ARE UNCALIBRATED ASSUMPTIONS, not values fitted to Bengaluru flood records.
Override per city under a "floodlens" key in packages/city-config/<city>.json."""
from __future__ import annotations

import json
import os
from pathlib import Path

from pydantic import BaseModel

DEFAULT_DIR = Path(__file__).resolve().parents[3] / "packages" / "city-config"


class Settings(BaseModel):
    grid_spacing_m: float = 250
    pad_m: float = 1500                # grid extends this far beyond the monitored routes
    max_cells: int = 900
    relief_radius_cells: int = 3       # compare each cell with neighbours this many cells away
    relief_full_m: float = 6.0         # relief (how much lower than surroundings) that counts as fully depressed
    accum6_lo_mm: float = 15           # 6 h rainfall below this adds no rain score
    accum6_hi_mm: float = 75           # ... and at or above this gives the full rain score
    peak_lo_mm_h: float = 8
    peak_hi_mm_h: float = 40
    base_exposure: float = 0.2         # share of the rain score that applies even on flat ground
    alert_min_risk: float = 0.25
    bands: list[tuple[float, str]] = [(0.8, "critical"), (0.6, "high"), (0.4, "moderate"), (0.25, "low")]
    report_ttl_h: float = 6
    report_radius_m: float = 250
    report_risk: float = 0.7
    route_corridor_m: float = 100
    base_confidence: float = 0.35      # a model estimate without validation is not high-confidence
    report_confidence: float = 0.55
    scenario_accum6_mm: float = 70     # "what-if heavy rain" preset (not a forecast)
    scenario_peak_mm_h: float = 35


def load_settings(city: str | None = None) -> Settings:
    city = city or os.environ.get("NAMMAPULSE_CITY", "bengaluru")
    path = Path(os.environ.get("NAMMAPULSE_CITY_DIR", DEFAULT_DIR)) / f"{city}.json"
    try:
        return Settings.model_validate(json.loads(path.read_text()).get("floodlens", {}))
    except FileNotFoundError:
        return Settings()
