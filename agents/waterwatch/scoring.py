"""
Deterministic severity scoring engine.
No randomness, no LLM. Inputs are observable facts; output is a Severity enum value.
Thresholds are loaded from config/city.json — never hardcoded here.
"""
import json
import os
from pathlib import Path
from contracts.agent_contract import Severity

# Load thresholds from city config
_CONFIG_PATH = Path(__file__).parent.parent.parent / "config" / "city.json"

def _load_thresholds() -> dict:
    with open(_CONFIG_PATH, "r") as f:
        cfg = json.load(f)
    return cfg["severityThresholds"]

_THRESHOLDS = _load_thresholds()


def compute_severity(
    incident_type: str,
    duration_hrs: float,
    report_count: int,
    area_km2: float,
    sensor_deviation: float,
) -> Severity:
    """
    Compute severity for a water incident from observable facts.
    Returns Severity enum value. Never returns a random result.
    """
    if incident_type == "sensor_anomaly":
        t = _THRESHOLDS["sensor_anomaly"]
        if sensor_deviation >= t["sensorDeviationCritical"]:
            return Severity.critical
        if sensor_deviation >= t["sensorDeviationHigh"]:
            return Severity.high
        if sensor_deviation >= t["sensorDeviationModerate"]:
            return Severity.moderate
        if sensor_deviation >= t["sensorDeviationLow"]:
            return Severity.low
        return Severity.info

    # For supply_disruption, tanker_shortage, demand_spike use duration + report count
    key = incident_type if incident_type in _THRESHOLDS else "supply_disruption"
    t = _THRESHOLDS[key]

    if duration_hrs >= t["critical"]["durationHrs"] or report_count >= t["critical"]["reportCount"]:
        return Severity.critical
    if duration_hrs >= t["high"]["durationHrs"] or report_count >= t["high"]["reportCount"]:
        return Severity.high
    if duration_hrs >= t["moderate"]["durationHrs"] or report_count >= t["moderate"]["reportCount"]:
        return Severity.moderate
    if duration_hrs >= t["low"]["durationHrs"] or report_count >= t["low"]["reportCount"]:
        return Severity.low
    return Severity.info


def compute_confidence(report_count: int, is_simulated: bool, sensor_deviation: float) -> float:
    """
    Compute a confidence score 0.0–1.0 based on corroboration signals.
    Pure function, no randomness.
    """
    if is_simulated:
        return 0.75  # fixed demo confidence

    base = 0.5
    # More reports → higher confidence, capped at 0.95
    report_boost = min(report_count * 0.05, 0.40)
    # Sensor data adds confidence
    sensor_boost = sensor_deviation * 0.10
    return min(round(base + report_boost + sensor_boost, 3), 0.95)
