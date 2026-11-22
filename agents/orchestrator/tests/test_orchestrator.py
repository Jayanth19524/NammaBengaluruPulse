from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from orchestrator.api import create_app
from orchestrator.clients import AgentUnavailable
from orchestrator.config import Settings
from orchestrator.graph import Orchestrator
from orchestrator.models import MonitoredRoute, RunRequest
from orchestrator.store import Store

T0 = datetime(2026, 11, 23, 2, 30, tzinfo=timezone.utc)
GEOM = [[77.60, 12.90], [77.65, 12.90]]


def route(id="r1", **kw):
    return MonitoredRoute(id=id, name=kw.pop("name", "Commute"), origin=(12.9, 77.6), destination=(12.9, 77.65), **kw)


def plan(predicted=3000, snapshot=1800, free=1500, alt_predicted=None, live=None):
    prim = {"id": "route-1", "geometry": GEOM, "via": ["Outer Ring Road"], "warnings": [],
            "prediction": {"predicted_s": predicted, "snapshot_s": snapshot, "free_flow_s": free,
                           "low_s": predicted * 0.9, "high_s": predicted * 1.1, "basis": "assumed time-of-day profile"}}
    routes = [prim]
    if alt_predicted:
        routes.append({"id": "route-2", "geometry": GEOM, "via": ["Hosur Road"], "warnings": [],
                       "prediction": {**prim["prediction"], "predicted_s": alt_predicted, "free_flow_s": free + 100}})
    return {"routes": routes, "live_traffic": live}


def incident(id="i1", route_id="r1", d=10, sev="high", basis="reported", sim=False, kind="pothole", lat=12.9, lon=77.62, conf=0.6):
    return {"agent": "RoadTrust", "incident_id": id, "incident_type": kind, "location": {"latitude": lat, "longitude": lon},
            "severity": sev, "confidence": conf, "verification_status": basis, "affected_route": True, "route_id": route_id,
            "distance_m": d, "evidence": [], "source": ["Community report"], "recommended_action": "Slow down.",
            "observed_at": "2026-11-22T10:00:00Z", "is_simulated": sim}


class FakeTrip:
    def __init__(self, result=None, fail=False):
        self.result, self.fail, self.calls = result or plan(), fail, 0

    def plan(self, o, d, depart_at):
        self.calls += 1
        if self.fail:
            raise AgentUnavailable("down")
        return self.result


class FakeRoad:
    def __init__(self, responses=(), fail=False, health=None):
        self.responses, self.fail, self.sent = list(responses), fail, None
        self.health = health or [{"source": "OpenStreetMap", "status": "ok"}]

    def investigate(self, routes):
        self.sent = routes
        if self.fail:
            raise AgentUnavailable("down")
        return {"responses": self.responses, "source_health": self.health, "audit": {}}


def make(trip=None, road=None, settings=None, clock=None, store=None):
    clock = clock or (lambda: T0)
    return Orchestrator(trip or FakeTrip(), road or FakeRoad(), store or Store(), settings or Settings(), clock)


def actions(run):
    return {d["key"]: d["action"] for d in run["decisions"]}


def reason(run, key):
    return next(d for d in run["decisions"] if d["key"] == key)["reasons"][0]


def test_happy_path_alerts_ranked_with_reasons_and_alternative():
    o = make(FakeTrip(plan(alt_predicted=2500)), FakeRoad([incident("i1", d=10, sev="high"), incident("i2", d=48, sev="low", lat=12.9, lon=77.63)]))
    run = o.run(RunRequest(routes=[route()]))
    assert actions(run) == {"traffic:r1": "alert", "road:i1": "alert", "road:i2": "suppress"}
    assert "below" in reason(run, "road:i2") or "relevance" in reason(run, "road:i2")
    alerts = [d for d in run["decisions"] if d["action"] == "alert"]
    assert [a["rank"] for a in alerts] == [1, 2]
    assert alerts[0]["finding"]["score"] >= alerts[1]["finding"]["score"]
    traffic = next(a for a in alerts if a["key"] == "traffic:r1")["finding"]
    assert traffic["basis"] == "predicted" and "Hosur Road" in traffic["action"] and "8 min faster" in traffic["action"]
    assert run["summary"]["alerts"] == 2
    nodes = [e["node"] for e in run["events"]]
    assert nodes[0] == "plan_regions" and nodes[-1] == "record" and {"trip", "road", "normalize", "dedupe", "score", "decide"} <= set(nodes)


def test_decisions_include_score_breakdown():
    run = make(road=FakeRoad([incident()])).run(RunRequest(routes=[route(categories=["road"])]))
    f = run["decisions"][0]["finding"]
    assert set(f["score_parts"]) == {"severity", "proximity", "basis", "confidence"}
    assert f["score"] == pytest.approx(0.4 * 0.85 + 0.25 * 0.8 + 0.2 * 0.7 + 0.15 * 0.6, abs=0.001)


def test_roadtrust_receives_geometry_from_tripcast():
    road = FakeRoad()
    make(road=road).run(RunRequest(routes=[route()]))
    assert road.sent[0]["id"] == "r1" and len(road.sent[0]["geometry"]) == 2


def test_dedupes_same_incident_across_routes_and_near_duplicates():
    road = FakeRoad([incident("i1", route_id="r1", d=20), incident("i1", route_id="r2", d=5),
                     incident("i9", route_id="r1", d=12, lat=12.90005, lon=77.62005)])
    run = make(road=road).run(RunRequest(routes=[route("r1", categories=["road"]), route("r2", categories=["road"])]))
    assert len(run["decisions"]) == 1
    f = run["decisions"][0]["finding"]
    assert sorted(f["route_ids"]) == ["r1", "r2"] and f["distance_m"] == 5
    assert sum(e["node"] == "dedupe" and e["message"].startswith("Merged") for e in run["events"]) == 2


def test_simulated_findings_are_excluded_unless_requested():
    road = FakeRoad([incident(sim=True)])
    r = make(road=road).run(RunRequest(routes=[route(categories=["road"])]))
    assert actions(r) == {"road:i1": "suppress"} and "simulated" in reason(r, "road:i1")
    r2 = make(road=FakeRoad([incident(sim=True)])).run(RunRequest(routes=[route(categories=["road"])], include_simulated=True))
    assert actions(r2) == {"road:i1": "alert"}


def test_user_preferences_category_and_min_severity():
    road = FakeRoad([incident(sev="moderate")])
    off = make(FakeTrip(plan(3000, 3000, 2900)), road).run(RunRequest(routes=[route(categories=["traffic"])]))
    assert actions(off) == {} and road.sent is None   # a disabled category is not even queried
    r = make(road=FakeRoad([incident(sev="moderate")])).run(RunRequest(routes=[route(categories=["road"], min_severity="high")]))
    assert actions(r) == {"road:i1": "suppress"} and "below your minimum" in reason(r, "road:i1")


def test_cooldown_suppresses_repeat_then_allows_after_expiry_or_escalation():
    store = Store()
    t = [T0]
    req = lambda: RunRequest(routes=[route(categories=["road"])])
    def run(sev="high"):
        return make(road=FakeRoad([incident(sev=sev)]), store=store, clock=lambda: t[0]).run(req())
    assert actions(run()) == {"road:i1": "alert"}
    t[0] = T0 + timedelta(hours=1)
    second = run()
    assert actions(second) == {"road:i1": "suppress"} and "already alerted" in reason(second, "road:i1")
    t[0] = T0 + timedelta(hours=2)
    assert actions(run("critical")) == {"road:i1": "alert"}       # escalation breaks cooldown
    t[0] = T0 + timedelta(hours=9)
    assert actions(run("critical")) == {"road:i1": "alert"}       # cooldown expired


def test_per_run_cap_keeps_highest_priority():
    inc = [incident(f"i{n}", d=5, sev="critical", lat=12.9, lon=77.60 + n * 0.005) for n in range(4)]
    s = Settings(max_alerts_per_run=2)
    run = make(road=FakeRoad(inc), settings=s).run(RunRequest(routes=[route(categories=["road"])]))
    assert sum(d["action"] == "alert" for d in run["decisions"]) == 2
    assert "per run" in next(d for d in run["decisions"] if d["action"] == "suppress")["reasons"][0]


def test_no_notable_traffic_change_creates_no_finding():
    run = make(FakeTrip(plan(1900, 1800, 1500))).run(RunRequest(routes=[route()]))
    assert run["decisions"] == []
    assert any("no notable traffic change" in e["message"] for e in run["events"])
    assert run["summary"]["headline"] == "Nothing needs your attention"


def test_tripcast_down_degrades_and_uses_supplied_geometry():
    r = route(categories=["road"]).model_copy(update={"geometry": [(77.6, 12.9), (77.65, 12.9)]})
    road = FakeRoad([incident()])
    run = make(FakeTrip(fail=True), road).run(RunRequest(routes=[r]))
    assert actions(run) == {"road:i1": "alert"}
    assert "TripCast" in run["summary"]["headline"] and any(e["level"] == "warn" for e in run["events"])


def test_everything_down_still_records_the_run():
    store = Store()
    run = make(FakeTrip(fail=True), FakeRoad(fail=True), store=store).run(RunRequest(routes=[route()]))
    assert run["decisions"] == [] and "nothing could be checked" in run["summary"]["headline"]
    assert store.get_run(run["id"]) is not None and store.list_runs()[0]["id"] == run["id"]


def test_degraded_road_source_is_noted_not_hidden():
    road = FakeRoad([incident()], health=[{"source": "OpenStreetMap", "status": "degraded"}])
    run = make(road=road).run(RunRequest(routes=[route(categories=["road"])]))
    assert any("degraded" in e["message"] for e in run["events"])
    assert "OpenStreetMap" in run["summary"]["headline"]


def test_api_run_and_history(tmp_path):
    orch = make(road=FakeRoad([incident()]), store=Store(str(tmp_path / "o.db")))
    c = TestClient(create_app(orch))
    assert c.get("/health").json()["framework"] == "langgraph"
    body = {"routes": [{"id": "r1", "name": "Commute", "origin": [12.9, 77.6], "destination": [12.9, 77.65]}]}
    run = c.post("/run", json=body).json()
    assert run["summary"]["alerts"] >= 1
    assert c.get(f"/runs/{run['id']}").json()["events"]
    assert c.get("/runs").json()[0]["id"] == run["id"]
    assert len(c.get("/alerts").json()) >= 1
    assert c.get("/runs/nope").status_code == 404
