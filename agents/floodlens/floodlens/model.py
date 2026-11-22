"""The flood-risk model: deterministic and explainable. It is a heuristic, not a hydrological simulation and it
has not been validated against real flood records. Rainfall alone never produces a high score: it is combined
with how much lower than its surroundings a place sits (water collects in depressions)."""
from __future__ import annotations

from .config import Settings
from .models import Cell, RainStats


def clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def rain_score(r: RainStats, s: Settings) -> float:
    a = clamp01((r.accum_6h_mm - s.accum6_lo_mm) / (s.accum6_hi_mm - s.accum6_lo_mm))
    p = clamp01((r.peak_mm_h - s.peak_lo_mm_h) / (s.peak_hi_mm_h - s.peak_lo_mm_h))
    return max(a, p)


def depression(relief_m: float, s: Settings) -> float:
    return clamp01(relief_m / s.relief_full_m)


def severity(risk: float, s: Settings) -> str:
    for lo, name in s.bands:
        if risk >= lo:
            return name
    return "info"


def score_cell(cell: Cell, rain: RainStats, s: Settings, reported: bool = False) -> Cell:
    cell.depression = round(depression(cell.relief_m, s), 3)
    cell.rain_score = round(rain_score(rain, s), 3)
    risk = cell.rain_score * (s.base_exposure + (1 - s.base_exposure) * cell.depression)
    if reported:  # a recent nearby waterlogging report is direct evidence; the model cannot talk it down
        risk = max(risk, s.report_risk)
        cell.reported = True
    cell.risk = round(risk, 3)
    cell.severity = severity(cell.risk, s)
    return cell


def compute_relief(rows_elev: list[list[float]], radius: int) -> list[list[float]]:
    """relief = mean elevation of surrounding cells minus own elevation (positive: a local low)."""
    h, w = len(rows_elev), len(rows_elev[0])
    out = []
    for i in range(h):
        row = []
        for j in range(w):
            vals = [rows_elev[a][b] for a in range(max(0, i - radius), min(h, i + radius + 1))
                    for b in range(max(0, j - radius), min(w, j + radius + 1)) if (a, b) != (i, j)]
            row.append(round(sum(vals) / len(vals) - rows_elev[i][j], 2) if vals else 0.0)
        out.append(row)
    return out
