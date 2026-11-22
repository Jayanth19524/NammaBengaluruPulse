"""
WaterWatch agent — orchestrates adapter → score → template → validated contract.
"""
import logging
from datetime import datetime, timezone
from typing import List

from contracts.agent_contract import (
    AgentContract,
    AgentName,
    Location,
    Severity,
    VerificationStatus,
)
from adapters.base import RawWaterData
from adapters.mock_adapter import MockAdapter
from adapters.bwssb_adapter import BWSSBAdapter
from adapters.sensor_adapter import SensorAdapter
from scoring import compute_severity, compute_confidence
from alert_templates import get_recommended_action

logger = logging.getLogger(__name__)


def _pick_verification_status(raw: RawWaterData) -> VerificationStatus:
    if raw.report_count >= 5:
        return VerificationStatus.confirmed
    if raw.report_count >= 1:
        return VerificationStatus.reported
    if raw.sensor_deviation > 0:
        return VerificationStatus.predicted
    return VerificationStatus.predicted


def _build_contract(raw: RawWaterData) -> AgentContract:
    severity = compute_severity(
        incident_type=raw.incident_type,
        duration_hrs=raw.duration_hrs,
        report_count=raw.report_count,
        area_km2=raw.area_km2,
        sensor_deviation=raw.sensor_deviation,
    )
    confidence = compute_confidence(
        report_count=raw.report_count,
        is_simulated=raw.is_simulated,
        sensor_deviation=raw.sensor_deviation,
    )
    recommended_action = get_recommended_action(
        incident_type=raw.incident_type,
        severity=severity,
        area_name=raw.area_name,
        duration_hrs=raw.duration_hrs,
    )
    return AgentContract(
        agent=AgentName.WaterWatch,
        incident_type=raw.incident_type,
        location=Location(latitude=raw.latitude, longitude=raw.longitude),
        severity=severity,
        confidence=confidence,
        verification_status=_pick_verification_status(raw),
        affected_route=False,  # WaterWatch monitors homes, not routes
        evidence=raw.evidence,
        source=raw.source,
        recommended_action=recommended_action,
        observed_at=datetime.now(timezone.utc),
        is_simulated=raw.is_simulated,
    )


class WaterWatchAgent:
    def __init__(self, use_mock: bool = True):
        self.use_mock = use_mock
        self._mock = MockAdapter()
        self._bwssb = BWSSBAdapter()
        self._sensor = SensorAdapter()

    async def scan(
        self, lat: float, lng: float, radius_m: float
    ) -> List[AgentContract]:
        if self.use_mock:
            raw_items = await self._mock.fetch(lat, lng, radius_m)
        else:
            # Merge results from real adapters; fall back to mock if all fail
            bwssb_items = await self._bwssb.fetch(lat, lng, radius_m)
            sensor_items = await self._sensor.fetch(lat, lng, radius_m)
            raw_items = bwssb_items + sensor_items
            if not raw_items:
                logger.warning(
                    "[WaterWatchAgent] All real adapters returned empty — falling back to mock"
                )
                raw_items = await self._mock.fetch(lat, lng, radius_m)

        contracts: List[AgentContract] = []
        for raw in raw_items:
            try:
                contracts.append(_build_contract(raw))
            except Exception as exc:
                logger.error(
                    "[WaterWatchAgent] Failed to build contract for %s: %s",
                    raw.incident_type, exc
                )
        return contracts
