"""RoadTrust agent: ingests reports, investigates monitored routes, returns contract responses."""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from .adapters.base import AdapterError, RoadAdapter
from .config import CityConfig
from .contract import AgentResponse, Location
from .detector import Detector
from .geo import distance_to_route_m, route_bbox
from .gps import GpsError, exif_gps, validate_coordinates
from .models import Incident, IncomingReport, Kind, Route, Severity
from .severity import classify
from .store import IncidentStore

ACTIONS = {
    "pothole": "Slow down and watch for the pothole, or take an alternative road.",
    "road_damage": "Expect a rough surface on this stretch; allow extra time.",
    "closure": "Check an alternative route before leaving.",
    "construction": "Expect lane restrictions and delays; allow extra time.",
    "other": "Check the details before travelling this stretch.",
}


def hash_reporter(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


class RoadTrustAgent:
    def __init__(self, city: CityConfig, store: IncidentStore, detector: Detector,
                 adapters: list[RoadAdapter] | None = None):
        self.city, self.store, self.detector = city, store, detector
        self.adapters = adapters or []

    # -- reports --------------------------------------------------------
    def submit_report(self, *, reporter: str, kind: Kind = "pothole", description: str = "",
                      latitude: float | None = None, longitude: float | None = None,
                      user_severity: Severity = "low", image: bytes | None = None,
                      now: datetime | None = None) -> tuple[Incident, bool, dict]:
        """Returns (incident, created, info). Raises GpsError on unusable location."""
        now = now or datetime.now(timezone.utc)
        s = self.city.roadtrust
        gps_source = "client"
        if image is not None and len(image) > s.max_image_bytes:
            raise ValueError("image too large")
        if (latitude is None or longitude is None) and image is not None:
            found = exif_gps(image)
            if found:
                latitude, longitude = found
                gps_source = "exif"
        lat, lon = validate_coordinates(latitude, longitude, self.city)

        severity, confidence = user_severity, 0.4
        evidence: list[dict] = [{"type": "user_report", "gps_source": gps_source}]
        analysis = {"cv_run": False, "note": "no photo"}
        if image is not None:
            result = self.detector.detect(image)
            analysis = {"cv_run": result.available, "note": result.note}
            if result.available:
                cv_sev = classify(result, s.min_detection_confidence)
                kept = [d for d in result.detections if d.confidence >= s.min_detection_confidence]
                evidence.append({"type": "cv_detection", "model": self.detector.name,
                                 "detections": [d.model_dump() for d in kept]})
                if cv_sev:
                    severity = cv_sev
                    confidence = max(d.confidence for d in kept)
                    analysis["result"] = "damage_detected"
                else:
                    analysis["result"] = "no_damage_detected"  # report kept, flagged for the user
            else:
                evidence.append({"type": "photo", "analysed": False})
        report = IncomingReport(
            kind=kind, latitude=lat, longitude=lon, severity=severity, description=description,
            reporter_id=hash_reporter(reporter), source="Community report", observed_at=now,
            confidence=confidence, evidence=evidence,
        )
        inc, created = self.store.ingest(report)
        return inc, created, analysis

    # -- investigation --------------------------------------------------
    def investigate(self, routes: list[Route], now: datetime | None = None) -> dict:
        now = now or datetime.now(timezone.utc)
        health: list[dict] = []
        for route in routes:
            pad = route.corridor_m or self.city.roadtrust.default_corridor_m
            bbox = route_bbox(route.geometry, pad)
            for adapter in self.adapters:
                try:
                    for rep in adapter.fetch(bbox, now):
                        self.store.ingest(rep)
                    health.append({"source": adapter.name, "status": "ok", "simulated": adapter.is_simulated})
                except AdapterError as exc:
                    health.append({"source": adapter.name, "status": "degraded", "error": str(exc)})
        active = self.store.active(now)
        responses: list[AgentResponse] = []
        for route in routes:
            corridor = route.corridor_m or self.city.roadtrust.default_corridor_m
            for inc in active:
                d = distance_to_route_m(inc.latitude, inc.longitude, route.geometry)
                if d <= corridor:
                    responses.append(self._to_response(inc, route.id, d))
        responses.sort(key=lambda r: (-_rank(r.severity), r.distance_m or 0))
        return {"responses": responses, "source_health": _dedupe_health(health),
                "audit": {"routes": len(routes), "active_incidents": len(active),
                          "relevant": len(responses), "at": now.isoformat()}}

    @staticmethod
    def _to_response(inc: Incident, route_id: str, distance: float) -> AgentResponse:
        evidence = [e for e in inc.evidence if not e.get("type") == "user_report"]
        evidence.append({"type": "report_count", "count": inc.report_count,
                         "note": "Distinct reporters; not independent verification"
                         if inc.verification_status == "reported" else "Official source"})
        if inc.repair_status == "repair_reported":
            evidence.append({"type": "repair_claim", "official": False,
                             "note": "Repair reported by users, not confirmed"})
        return AgentResponse(
            agent="RoadTrust", incident_id=inc.id, incident_type=inc.kind,
            location=Location(latitude=inc.latitude, longitude=inc.longitude),
            severity=inc.severity, confidence=inc.confidence,
            verification_status=inc.verification_status, affected_route=True,
            route_id=route_id, distance_m=round(distance, 1), evidence=evidence,
            source=inc.sources, recommended_action=ACTIONS[inc.kind],
            observed_at=inc.last_seen, is_simulated=inc.is_simulated,
        )


def _rank(s: str) -> int:
    return ["info", "low", "moderate", "high", "critical"].index(s)


def _dedupe_health(h: list[dict]) -> list[dict]:
    seen: dict[str, dict] = {}
    for item in h:
        prev = seen.get(item["source"])
        if prev is None or item["status"] == "degraded":
            seen[item["source"]] = item
    return list(seen.values())
