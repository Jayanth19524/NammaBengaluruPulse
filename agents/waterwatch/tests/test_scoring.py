"""
Unit tests for WaterWatch scoring engine.
No external dependencies — pure function tests.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from contracts.agent_contract import Severity
from scoring import compute_severity, compute_confidence


def test_supply_disruption_critical():
    s = compute_severity("supply_disruption", duration_hrs=24, report_count=10, area_km2=1.0, sensor_deviation=0.0)
    assert s == Severity.critical

def test_supply_disruption_high():
    s = compute_severity("supply_disruption", duration_hrs=12, report_count=5, area_km2=0.5, sensor_deviation=0.0)
    assert s == Severity.high

def test_supply_disruption_moderate():
    s = compute_severity("supply_disruption", duration_hrs=6, report_count=3, area_km2=0.3, sensor_deviation=0.0)
    assert s == Severity.moderate

def test_supply_disruption_low():
    s = compute_severity("supply_disruption", duration_hrs=2, report_count=1, area_km2=0.1, sensor_deviation=0.0)
    assert s == Severity.low

def test_supply_disruption_info():
    s = compute_severity("supply_disruption", duration_hrs=0.5, report_count=0, area_km2=0.0, sensor_deviation=0.0)
    assert s == Severity.info

def test_sensor_anomaly_critical():
    s = compute_severity("sensor_anomaly", duration_hrs=0, report_count=0, area_km2=0.0, sensor_deviation=0.9)
    assert s == Severity.critical

def test_sensor_anomaly_moderate():
    s = compute_severity("sensor_anomaly", duration_hrs=0, report_count=0, area_km2=0.0, sensor_deviation=0.35)
    assert s == Severity.moderate

def test_sensor_anomaly_info():
    s = compute_severity("sensor_anomaly", duration_hrs=0, report_count=0, area_km2=0.0, sensor_deviation=0.0)
    assert s == Severity.info

def test_confidence_simulated():
    c = compute_confidence(report_count=5, is_simulated=True, sensor_deviation=0.0)
    assert c == 0.75

def test_confidence_real_increases_with_reports():
    c0 = compute_confidence(report_count=0, is_simulated=False, sensor_deviation=0.0)
    c5 = compute_confidence(report_count=5, is_simulated=False, sensor_deviation=0.0)
    assert c5 > c0

def test_confidence_max():
    c = compute_confidence(report_count=100, is_simulated=False, sensor_deviation=1.0)
    assert c <= 0.95
