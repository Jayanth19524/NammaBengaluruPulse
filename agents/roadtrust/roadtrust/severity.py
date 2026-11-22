"""Deterministic severity classification from detections. No LLM involved."""
from __future__ import annotations

from .models import SEVERITY_ORDER, DetectionResult, Severity


def coverage_ratio(result: DetectionResult, min_conf: float) -> float:
    if not result.image_width or not result.image_height:
        return 0.0
    area = sum(
        max(0.0, d.bbox[2] - d.bbox[0]) * max(0.0, d.bbox[3] - d.bbox[1])
        for d in result.detections
        if d.confidence >= min_conf
    )
    return min(1.0, area / (result.image_width * result.image_height))


def classify(result: DetectionResult, min_conf: float) -> Severity | None:
    """Severity from how much of the frame is damaged, bumped one level when there
    are three or more separate detections. None when nothing credible was found."""
    kept = [d for d in result.detections if d.confidence >= min_conf]
    if not kept:
        return None
    ratio = coverage_ratio(result, min_conf)
    if ratio < 0.02:
        idx = 1  # low
    elif ratio < 0.06:
        idx = 2  # moderate
    elif ratio < 0.15:
        idx = 3  # high
    else:
        idx = 4  # critical
    if len(kept) >= 3:
        idx += 1
    return SEVERITY_ORDER[min(idx, 4)]
