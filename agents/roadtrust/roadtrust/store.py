"""Incident store with duplicate detection and repair tracking.
InMemoryStore is for tests/demo; a PostGIS-backed store implements the same methods."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Protocol

from .geo import haversine_m
from .models import SEVERITY_ORDER, IncomingReport, Incident, RepairEvent, RepairStatus


class IncidentStore(Protocol):
    def ingest(self, report: IncomingReport) -> tuple[Incident, bool]: ...
    def get(self, incident_id: str) -> Incident | None: ...
    def active(self, now: datetime) -> list[Incident]: ...
    def update_repair(self, incident_id: str, status: RepairStatus, source: str, official: bool, at: datetime) -> Incident: ...


class InMemoryStore:
    def __init__(self, dedup_radius_m: float = 25, stale_after_days: int = 30):
        self._items: dict[str, Incident] = {}
        self.dedup_radius_m = dedup_radius_m
        self.stale_after = timedelta(days=stale_after_days)

    def _find_duplicate(self, r: IncomingReport) -> Incident | None:
        best, best_d = None, self.dedup_radius_m
        for inc in self._items.values():
            if inc.kind != r.kind or inc.repair_status == "repaired" or inc.is_simulated != r.is_simulated:
                continue
            d = haversine_m(inc.latitude, inc.longitude, r.latitude, r.longitude)
            if d <= best_d:
                best, best_d = inc, d
        return best

    def ingest(self, r: IncomingReport) -> tuple[Incident, bool]:
        """Returns (incident, created). A repeat report by the same reporter does not
        inflate the report count."""
        dup = self._find_duplicate(r)
        if dup is None:
            inc = Incident(
                id=uuid.uuid4().hex, kind=r.kind, latitude=r.latitude, longitude=r.longitude,
                severity=r.severity, verification_status=r.verification_status,
                first_seen=r.observed_at, last_seen=r.observed_at, reporter_ids={r.reporter_id},
                description=r.description, sources=[r.source], evidence=list(r.evidence),
                confidence=r.confidence, is_simulated=r.is_simulated, expires_at=r.expires_at,
            )
            self._items[inc.id] = inc
            return inc, True
        if r.reporter_id not in dup.reporter_ids:
            dup.reporter_ids.add(r.reporter_id)
            dup.report_count += 1
        dup.last_seen = max(dup.last_seen, r.observed_at)
        if SEVERITY_ORDER.index(r.severity) > SEVERITY_ORDER.index(dup.severity):
            dup.severity = r.severity
        if r.source not in dup.sources:
            dup.sources.append(r.source)
        dup.evidence.extend(r.evidence)
        dup.confidence = max(dup.confidence, r.confidence)
        if r.verification_status == "confirmed":
            dup.verification_status = "confirmed"
        if r.expires_at:
            dup.expires_at = r.expires_at
        return dup, False

    def get(self, incident_id: str) -> Incident | None:
        return self._items.get(incident_id)

    def active(self, now: datetime) -> list[Incident]:
        out = []
        for inc in self._items.values():
            if inc.repair_status == "repaired":
                continue
            if inc.expires_at and inc.expires_at < now:
                continue
            if now - inc.last_seen > self.stale_after:
                continue
            out.append(inc)
        return out

    def update_repair(self, incident_id, status, source, official, at) -> Incident:
        inc = self._items[incident_id]
        # Only an official source can mark a road as repaired / confirmed.
        effective: RepairStatus = status
        if status == "repaired" and not official:
            effective = "repair_reported"
        inc.repair_status = effective
        if effective == "repaired":
            inc.verification_status = "confirmed"
        inc.repair_history.append(RepairEvent(status=effective, at=at, source=source, official=official))
        return inc
