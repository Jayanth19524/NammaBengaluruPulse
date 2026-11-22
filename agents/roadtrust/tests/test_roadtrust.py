import io
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from roadtrust.adapters.base import AdapterError
from roadtrust.adapters.mock import MockRoadAdapter
from roadtrust.adapters.overpass import OverpassAdapter
from roadtrust.agent import RoadTrustAgent
from roadtrust.api import create_app
from roadtrust.config import load_city
from roadtrust.contract import AgentResponse
from roadtrust.detector import NullDetector
from roadtrust.geo import distance_to_route_m, haversine_m
from roadtrust.gps import GpsError, exif_gps, validate_coordinates
from roadtrust.models import Detection, DetectionResult, Route
from roadtrust.severity import classify
from roadtrust.store import InMemoryStore

NOW = datetime(2026, 11, 22, 12, 0, tzinfo=timezone.utc)
CITY = load_city()
# East-west route along lat 12.9177 passing the first mock incident.
ROUTE = Route(id="r1", name="demo", geometry=[(77.60, 12.9177), (77.65, 12.9177)])


class FakeDetector:
    name, available = "fake", True

    def __init__(self, dets, w=1000, h=1000):
        self.res = DetectionResult(available=True, detections=dets, image_width=w, image_height=h)

    def detect(self, image_bytes):
        return self.res


def make_agent(detector=None, adapters=None):
    s = CITY.roadtrust
    return RoadTrustAgent(CITY, InMemoryStore(s.dedup_radius_m, s.stale_after_days),
                          detector or NullDetector(), adapters or [])


def png(w=100, h=100):
    b = io.BytesIO()
    Image.new("RGB", (w, h)).save(b, "PNG")
    return b.getvalue()


# geo ------------------------------------------------------------------
def test_distance_to_route_is_metric():
    # ~0.0009 deg lat is ~100 m
    d = distance_to_route_m(12.9186, 77.62, ROUTE.geometry)
    assert 95 < d < 105
    assert distance_to_route_m(12.9177, 77.62, ROUTE.geometry) < 0.5


def test_haversine_matches_projection():
    a = haversine_m(12.9177, 77.60, 12.9186, 77.60)
    assert 95 < a < 105


# gps ------------------------------------------------------------------
def test_validate_coordinates_rejects_bad_values():
    for lat, lon in [(None, 77.6), (0, 0), (95, 77.6), (28.6, 77.2)]:  # last is Delhi, outside coverage
        with pytest.raises(GpsError):
            validate_coordinates(lat, lon, CITY)
    assert validate_coordinates(12.95, 77.6, CITY) == (12.95, 77.6)


def test_exif_gps_roundtrip():
    img = Image.new("RGB", (10, 10))
    exif = Image.Exif()
    gps = {1: "N", 2: (12.0, 55.0, 3.72), 3: "E", 4: (77.0, 37.0, 25.68)}
    exif[0x8825] = gps
    b = io.BytesIO()
    img.save(b, "JPEG", exif=exif)
    lat, lon = exif_gps(b.getvalue())
    assert lat == pytest.approx(12.9177, abs=1e-4)
    assert lon == pytest.approx(77.6238, abs=1e-4)
    assert exif_gps(png()) is None


# severity -------------------------------------------------------------
def test_severity_classification():
    def r(boxes):
        return DetectionResult(available=True, image_width=100, image_height=100,
                               detections=[Detection(label="pothole", confidence=c, bbox=b) for b, c in boxes])
    assert classify(r([]), 0.4) is None
    assert classify(r([((0, 0, 50, 50), 0.3)]), 0.4) is None            # below confidence
    assert classify(r([((0, 0, 10, 10), 0.9)]), 0.4) == "low"            # 1%
    assert classify(r([((0, 0, 20, 20), 0.9)]), 0.4) == "moderate"       # 4%
    assert classify(r([((0, 0, 30, 30), 0.9)]), 0.4) == "high"           # 9%
    assert classify(r([((0, 0, 50, 50), 0.9)]), 0.4) == "critical"       # 25%
    three = [((0, 0, 5, 5), 0.9)] * 3   # 0.75% total
    assert classify(r(three), 0.4) == "moderate"                         # low bumped by count


# reports, dedup, honesty ----------------------------------------------
def test_duplicate_reports_merge_and_same_reporter_does_not_inflate():
    a = make_agent()
    i1, c1, _ = a.submit_report(reporter="u1", latitude=12.9177, longitude=77.6238, now=NOW)
    i2, c2, _ = a.submit_report(reporter="u2", latitude=12.91775, longitude=77.62385, now=NOW)  # ~7 m away
    i3, c3, _ = a.submit_report(reporter="u2", latitude=12.9177, longitude=77.6238, now=NOW)
    far, c4, _ = a.submit_report(reporter="u3", latitude=12.9200, longitude=77.6238, now=NOW)   # ~250 m
    assert c1 and not c2 and not c3 and c4
    assert i1.id == i2.id == i3.id != far.id
    assert i1.report_count == 2
    assert i1.verification_status == "reported"  # user reports are never "confirmed"


def test_no_model_means_no_claim_of_analysis():
    a = make_agent()
    inc, _, analysis = a.submit_report(reporter="u", latitude=12.95, longitude=77.6, image=png(), now=NOW)
    assert analysis["cv_run"] is False
    assert {"type": "photo", "analysed": False} in inc.evidence


def test_cv_sets_severity_but_not_verification():
    dets = [Detection(label="pothole", confidence=0.9, bbox=(0, 0, 500, 500))]
    a = make_agent(FakeDetector(dets))
    inc, _, analysis = a.submit_report(reporter="u", latitude=12.95, longitude=77.6, image=png(), now=NOW)
    assert analysis["result"] == "damage_detected"
    assert inc.severity == "critical"
    assert inc.verification_status == "reported"


def test_oversize_image_rejected():
    a = make_agent()
    with pytest.raises(ValueError):
        a.submit_report(reporter="u", latitude=12.95, longitude=77.6, image=b"x" * (9 * 1024 * 1024))


# repair ---------------------------------------------------------------
def test_user_cannot_mark_repaired_only_official_can():
    a = make_agent()
    inc, _, _ = a.submit_report(reporter="u", latitude=12.9177, longitude=77.6238, now=NOW)
    a.store.update_repair(inc.id, "repaired", "user claim", False, NOW)
    assert inc.repair_status == "repair_reported" and inc.verification_status == "reported"
    assert a.store.active(NOW)  # still shown
    a.store.update_repair(inc.id, "repaired", "BBMP work order", True, NOW)
    assert inc.repair_status == "repaired" and inc.verification_status == "confirmed"
    assert not a.store.active(NOW)


def test_stale_reports_expire():
    a = make_agent()
    a.submit_report(reporter="u", latitude=12.9177, longitude=77.6238, now=NOW)
    assert a.store.active(NOW + timedelta(days=29))
    assert not a.store.active(NOW + timedelta(days=31))


# investigation --------------------------------------------------------
def test_investigate_only_returns_incidents_in_corridor_and_validates_contract():
    a = make_agent()
    a.submit_report(reporter="u1", latitude=12.91775, longitude=77.62, now=NOW)   # ~5 m from route
    a.submit_report(reporter="u2", latitude=12.9200, longitude=77.62, now=NOW)    # ~255 m, outside 50 m
    out = a.investigate([ROUTE], now=NOW)
    assert len(out["responses"]) == 1
    r = out["responses"][0]
    AgentResponse.model_validate(r.model_dump())
    assert r.agent == "RoadTrust" and r.route_id == "r1" and r.distance_m < 50
    assert r.verification_status == "reported" and r.is_simulated is False


def test_corridor_width_is_per_route():
    a = make_agent()
    a.submit_report(reporter="u", latitude=12.9200, longitude=77.62, now=NOW)  # ~255 m
    wide = ROUTE.model_copy(update={"corridor_m": 300})
    assert len(a.investigate([wide], now=NOW)["responses"]) == 1


def test_mock_adapter_is_labelled_simulated_and_filtered_by_bbox():
    a = make_agent(adapters=[MockRoadAdapter()])
    out = a.investigate([ROUTE], now=NOW)
    assert [r.incident_type for r in out["responses"]] == ["pothole"]  # m1 only; m2/m3 off-route
    assert out["responses"][0].is_simulated is True
    assert out["source_health"][0]["simulated"] is True


class BrokenAdapter:
    name, is_simulated = "broken", False

    def fetch(self, bbox, now):
        raise AdapterError("down")


def test_adapter_failure_degrades_gracefully():
    a = make_agent(adapters=[BrokenAdapter(), MockRoadAdapter()])
    out = a.investigate([ROUTE], now=NOW)
    status = {h["source"]: h["status"] for h in out["source_health"]}
    assert status["broken"] == "degraded"
    assert len(out["responses"]) == 1  # still produced results from the working source


def test_overpass_parsing_and_failure():
    payload = {"elements": [
        {"id": 1, "center": {"lat": 12.9177, "lon": 77.62}, "tags": {"highway": "construction", "name": "Flyover"}},
        {"id": 2, "tags": {}},  # no center: skipped
    ]}
    ok = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json=payload)))
    reps = OverpassAdapter(client=ok).fetch((77.6, 12.9, 77.7, 13.0), NOW)
    assert len(reps) == 1 and reps[0].kind == "construction" and not reps[0].is_simulated
    bad = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(503)))
    with pytest.raises(AdapterError):
        OverpassAdapter(client=bad).fetch((77.6, 12.9, 77.7, 13.0), NOW)


# api ------------------------------------------------------------------
def test_api_flow():
    client = TestClient(create_app(make_agent(adapters=[MockRoadAdapter()])))
    assert client.get("/health").json()["detector_available"] is False
    r = client.post("/reports", data={"lat": 12.91775, "lon": 77.62, "reporter_id": "alice",
                                      "severity": "moderate"}, files={"image": ("p.png", png(), "image/png")})
    assert r.status_code == 201
    body = r.json()
    assert "reporter_ids" not in body["incident"]            # privacy: no reporter identity leaked
    assert body["analysis"]["cv_run"] is False
    bad = client.post("/reports", data={"lat": 0, "lon": 0, "reporter_id": "alice"})
    assert bad.status_code == 422
    inv = client.post("/investigate", json={"routes": [ROUTE.model_dump()]}).json()
    assert len(inv["responses"]) == 2                         # user report + mock pothole
    iid = body["incident"]["id"]
    rep = client.post(f"/incidents/{iid}/repair", json={"status": "repaired", "source": "user"}).json()
    assert rep["repair_status"] == "repair_reported"
    assert client.post("/incidents/nope/repair", json={"status": "repaired", "source": "x"}).status_code == 404


def test_repeated_investigations_do_not_pile_up_evidence():
    a = make_agent(adapters=[MockRoadAdapter()])
    for _ in range(5):
        a.investigate([ROUTE], now=NOW)
    r = a.investigate([ROUTE], now=NOW)["responses"][0]
    assert r.evidence.count({"type": "report_count", "count": 1, "note": "Distinct reporters; not independent verification"}) == 1
    assert len(r.evidence) == 1
