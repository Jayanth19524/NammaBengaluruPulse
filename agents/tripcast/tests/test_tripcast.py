from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import httpx
import pytest
from fastapi.testclient import TestClient

from tripcast.api import create_app
from tripcast.live import TomTomLive
from tripcast.models import CandidateRoute, Step
from tripcast.planner import Planner, RoadIncidents
from tripcast.predictor import Predictor
from tripcast.profile import CongestionProfile
from tripcast.routing import OsrmRouter, RoutingError

IST = ZoneInfo("Asia/Kolkata")
FLAT = CongestionProfile([1.0] * 24, [1.0] * 24)


def route(n_steps=6, step_s=300, mid=(77.6, 12.9)):
    steps = [Step(free_flow_s=step_s, distance_m=2000, name=f"Road {i}", mid=(mid[0] + i * 0.01, mid[1])) for i in range(n_steps)]
    return CandidateRoute(steps=steps, geometry=[(77.6, 12.9), (77.7, 12.9)])


def test_profile_interpolates_and_weekend_differs():
    p = CongestionProfile()
    mon_8 = datetime(2026, 11, 23, 8, 0, tzinfo=IST)
    assert p.multiplier(mon_8) == pytest.approx(1.9)
    assert 1.9 < p.multiplier(mon_8 + timedelta(minutes=30)) < 2.0   # between 08:00 and 09:00
    sat_8 = datetime(2026, 11, 28, 8, 0, tzinfo=IST)
    assert p.multiplier(sat_8) < p.multiplier(mon_8)


def test_flat_profile_equals_free_flow():
    pr = Predictor(FLAT).predict(route(), datetime(2026, 11, 23, 3, 0, tzinfo=IST))
    assert pr.predicted_s == pr.free_flow_s == pr.snapshot_s == 1800


def test_traffic_building_during_trip_beats_departure_snapshot():
    # Leaves at 06:45 when it is quiet; most of the trip runs into the building peak.
    r = route(n_steps=12, step_s=300)  # 60 min free-flow
    depart = datetime(2026, 11, 23, 6, 45, tzinfo=IST)
    pr = Predictor(CongestionProfile()).predict(r, depart)
    assert pr.snapshot_s < pr.predicted_s          # a snapshot underestimates
    assert pr.predicted_s > 1.4 * pr.free_flow_s   # and the real trip is much slower than free flow
    assert pr.low_s < pr.predicted_s < pr.high_s
    assert pr.arrive_at > depart + timedelta(seconds=pr.snapshot_s)


def test_traffic_easing_during_trip_is_not_overestimated():
    r = route(n_steps=12, step_s=300)
    depart = datetime(2026, 11, 23, 9, 30, tzinfo=IST)   # peak easing off
    pr = Predictor(CongestionProfile()).predict(r, depart)
    assert pr.predicted_s < pr.snapshot_s


class FakeLive:
    name = "fake"

    def __init__(self, ratio):
        self.ratio = ratio

    def ratio_at(self, lon, lat):
        return self.ratio


def test_live_slowdown_raises_estimate_and_fades():
    r = route(n_steps=12, step_s=300)
    depart = datetime(2026, 11, 23, 13, 0, tzinfo=IST)   # profile 1.3
    base = Predictor(CongestionProfile()).predict(r, depart, now=depart)
    jam = Predictor(CongestionProfile(), FakeLive(2.6)).predict(r, depart, now=depart)  # twice the usual
    assert jam.predicted_s > base.predicted_s
    # Departing two hours later, today's jam should no longer be assumed.
    later = depart + timedelta(hours=2)
    far = Predictor(CongestionProfile(), FakeLive(2.6)).predict(r, later, now=depart)
    far_base = Predictor(CongestionProfile()).predict(r, later, now=depart)
    assert far.predicted_s == far_base.predicted_s
    assert "live traffic" in jam.basis and "assumed" in base.basis


def test_tomtom_adapter_parses_and_fails_soft():
    ok = httpx.Client(transport=httpx.MockTransport(lambda q: httpx.Response(
        200, json={"flowSegmentData": {"currentTravelTime": 150, "freeFlowTravelTime": 100}})))
    assert TomTomLive("k", client=ok).ratio_at(77.6, 12.9) == pytest.approx(1.5)
    bad = httpx.Client(transport=httpx.MockTransport(lambda q: httpx.Response(403)))
    assert TomTomLive("k", client=bad).ratio_at(77.6, 12.9) is None


OSRM = {"code": "Ok", "routes": [
    {"geometry": {"coordinates": [[77.6, 12.9], [77.7, 12.9]]}, "legs": [{"steps": [
        {"duration": 600, "distance": 8000, "name": "Outer Ring Road", "geometry": {"coordinates": [[77.6, 12.9], [77.65, 12.9]]}},
        {"duration": 0, "distance": 0, "name": "", "geometry": {"coordinates": []}}]}]},
    {"geometry": {"coordinates": [[77.6, 12.9], [77.7, 12.91]]}, "legs": [{"steps": [
        {"duration": 660, "distance": 8500, "name": "Hosur Road", "geometry": {"coordinates": [[77.6, 12.9], [77.65, 12.91]]}}]}]},
]}


def osrm_client():
    return httpx.Client(transport=httpx.MockTransport(lambda q: httpx.Response(200, json=OSRM)))


def test_osrm_parsing_skips_empty_steps():
    routes = OsrmRouter(client=osrm_client()).routes((12.9, 77.6), (12.9, 77.7))
    assert len(routes) == 2 and len(routes[0].steps) == 1 and routes[0].free_flow_s == 600


def test_osrm_failure_raises():
    bad = httpx.Client(transport=httpx.MockTransport(lambda q: httpx.Response(500)))
    with pytest.raises(RoutingError):
        OsrmRouter(client=bad).routes((12.9, 77.6), (12.9, 77.7))


def road_client(closure_on_route_1: bool):
    def handler(req):
        import json
        body = json.loads(req.content)
        resp = []
        if closure_on_route_1:
            resp.append({"route_id": "route-1", "incident_type": "closure", "severity": "high",
                         "verification_status": "reported", "distance_m": 3.0, "is_simulated": False,
                         "recommended_action": "Check an alternative route", "location": {"latitude": 12.9, "longitude": 77.62}})
        return httpx.Response(200, json={"responses": resp})
    return httpx.Client(transport=httpx.MockTransport(handler))


def make_planner(closure=False, incidents=True):
    inc = RoadIncidents("http://rt", client=road_client(closure)) if incidents else None
    return Planner(OsrmRouter(client=osrm_client()), Predictor(FLAT), inc)


def test_planner_recommends_fastest_and_lists_alternatives():
    out = make_planner().plan((12.9, 77.6), (12.9, 77.7), datetime(2026, 11, 23, 8, 0))
    routes = out["routes"]
    assert [r.recommended for r in routes] == [True, False]
    assert routes[0].via == ["Outer Ring Road"] and routes[1].delta_vs_best_s == 60
    assert out["road_incidents"] == "checked"


def test_reported_closure_demotes_fastest_route():
    out = make_planner(closure=True).plan((12.9, 77.6), (12.9, 77.7), datetime(2026, 11, 23, 8, 0))
    assert out["routes"][0].via == ["Hosur Road"]
    blocked = out["routes"][1]
    assert blocked.warnings[0]["kind"] == "closure" and blocked.incidents_on_route == 1


def test_roadtrust_down_is_reported_not_hidden():
    bad = httpx.Client(transport=httpx.MockTransport(lambda q: httpx.Response(500)))
    p = Planner(OsrmRouter(client=osrm_client()), Predictor(FLAT), RoadIncidents("http://rt", client=bad))
    out = p.plan((12.9, 77.6), (12.9, 77.7), datetime(2026, 11, 23, 8, 0))
    assert "unavailable" in out["road_incidents"]


def test_departure_options_never_in_the_past_and_best_time_visible():
    p = Planner(OsrmRouter(client=osrm_client()), Predictor(CongestionProfile()), None)
    now = p.local(None)
    out = p.plan((12.9, 77.6), (12.9, 77.7), None)
    assert all(d.depart_at >= now - timedelta(minutes=1) for d in out["departure_options"])
    assert out["departure_options"]


def test_api_plan():
    client = TestClient(create_app(make_planner()))
    assert client.get("/health").json()["profile"] == "assumed"
    r = client.post("/plan", json={"origin": [12.9, 77.6], "destination": [12.9, 77.7], "depart_at": "2026-11-23T08:00:00"})
    assert r.status_code == 200
    body = r.json()
    assert body["routes"][0]["recommended"] is True and body["live_traffic"] is None
    assert body["routes"][0]["prediction"]["basis"] == "assumed time-of-day profile"
