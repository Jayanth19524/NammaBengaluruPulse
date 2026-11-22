import json
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from agentkit import LLMReply, ScriptedLLM, ToolCall
from fastapi.testclient import TestClient

from floodlens.agent import FloodLensAgent, GpsError
from floodlens.api import create_app
from floodlens.config import Settings
from floodlens.llm_agent import FloodLensLLMAgent
from floodlens.model import compute_relief, depression, rain_score, score_cell
from floodlens.models import Cell, RainStats, Route, Scenario
from floodlens.sources import OpenMeteoElevation, OpenMeteoRain, SourceError, rain_stats

NOW = datetime(2026, 11, 23, 6, 0, tzinfo=timezone.utc)
S = Settings()
ROUTE = Route(id="r1", name="Commute", geometry=[(77.615, 12.9177), (77.635, 12.9177)])


class Bowl:
    """Elevation source: a bowl centred on the route, so the route crosses a real depression."""
    name = "fake elevation"

    def elevations(self, pts):
        return [900 + 40000 * ((lat - 12.9177) ** 2 + (lon - 77.625) ** 2) ** 0.5 * 100 / 100 for lat, lon in pts]


class Flat:
    name = "flat"

    def elevations(self, pts):
        return [900.0 for _ in pts]


class Rain:
    name = "fake forecast"

    def __init__(self, accum6=0.0, peak=0.0):
        self.accum6, self.peak = accum6, peak

    def forecast(self, pts):
        return [RainStats(lat=la, lon=lo, peak_mm_h=self.peak, accum_6h_mm=self.accum6, accum_24h_mm=self.accum6, hours=48) for la, lo in pts]


class BrokenRain:
    name = "broken forecast"

    def forecast(self, pts):
        raise SourceError("down")


def agent(elev=None, rain=None, settings=S):
    return FloodLensAgent(settings, elev or Bowl(), rain or Rain(70, 35), bbox=(77.35, 12.78, 77.85, 13.20))


# model ---------------------------------------------------------------------------
def test_rain_alone_is_never_high_risk_on_flat_ground():
    flat = Cell(id="a", lat=0, lon=0, elevation_m=900, relief_m=0)
    heavy = RainStats(lat=0, lon=0, peak_mm_h=60, accum_6h_mm=120, accum_24h_mm=150)
    assert score_cell(flat, heavy, S).risk == pytest.approx(S.base_exposure)
    assert flat.severity == "info"
    bowl = score_cell(Cell(id="b", lat=0, lon=0, elevation_m=890, relief_m=8), heavy, S)
    assert bowl.risk == 1.0 and bowl.severity == "critical"


def test_no_rain_means_no_risk_even_in_a_depression():
    c = score_cell(Cell(id="b", lat=0, lon=0, elevation_m=890, relief_m=8), RainStats(lat=0, lon=0, peak_mm_h=0, accum_6h_mm=0, accum_24h_mm=0), S)
    assert c.risk == 0 and c.severity == "info"


def test_score_components_scale():
    assert rain_score(RainStats(lat=0, lon=0, peak_mm_h=0, accum_6h_mm=45, accum_24h_mm=45), S) == pytest.approx(0.5)
    assert depression(3, S) == pytest.approx(0.5) and depression(-2, S) == 0


def test_relief_marks_local_lows():
    g = [[10, 10, 10], [10, 5, 10], [10, 10, 10]]
    r = compute_relief(g, 1)
    assert r[1][1] == 5 and r[0][0] < 0.5


def test_reported_waterlogging_sets_a_floor():
    c = score_cell(Cell(id="b", lat=0, lon=0, elevation_m=900, relief_m=0), RainStats(lat=0, lon=0, peak_mm_h=0, accum_6h_mm=0, accum_24h_mm=0), S, reported=True)
    assert c.risk == S.report_risk and c.reported and c.severity == "high"


# rainfall stats ------------------------------------------------------------------
def test_rain_stats_rolling_window_and_timing():
    times = [NOW + timedelta(hours=i) for i in range(12)]
    mm = [0, 0, 5, 20, 10, 5, 0, 0, 0, 0, 0, 0]
    r = rain_stats(12.9, 77.6, times, mm)
    assert r.peak_mm_h == 20 and r.accum_6h_mm == 40 and r.peak_at == times[3]
    assert r.window_start == times[2] and r.window_end == times[5] + timedelta(hours=1)


def test_open_meteo_parsing_and_failures():
    payload = [{"hourly": {"time": ["2026-11-23T00:00", "2026-11-23T01:00"], "precipitation": [1.0, 9.0]}}] * 2
    ok = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json=payload)))
    out = OpenMeteoRain(client=ok).forecast([(12.9, 77.6), (12.95, 77.65)])
    assert out[0].peak_mm_h == 9.0
    bad = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(500)))
    with pytest.raises(SourceError):
        OpenMeteoRain(client=bad).forecast([(12.9, 77.6)])
    calls = []

    def elev(r):
        calls.append(str(r.url))
        n = len(r.url.params["latitude"].split(","))
        return httpx.Response(200, json={"elevation": [float(i) for i in range(n)]})
    src = OpenMeteoElevation(client=httpx.Client(transport=httpx.MockTransport(elev)))
    pts = [(12.0 + i * 0.001, 77.0) for i in range(230)]
    assert len(src.elevations(pts)) == 230 and len(calls) == 3        # batched at 100 per request
    src.elevations(pts)
    assert len(calls) == 3                                              # cached


# agent ---------------------------------------------------------------------------
def test_heavy_rain_on_flat_terrain_raises_no_alert():
    out = agent(Flat(), Rain(70, 35)).run([ROUTE], now=NOW)
    assert out["responses"] == [] and out["audit"]["cells"] > 50 and out["forecast"]["available"] is True


def test_findings_are_labelled_predicted_with_honest_evidence():
    class Pit:
        name = "pit"

        def elevations(self, pts):
            return [880.0 if abs(lat - 12.9177) < 0.0012 and abs(lon - 77.625) < 0.0012 else 900.0 for lat, lon in pts]
    out = agent(Pit(), Rain(70, 35)).run([ROUTE], now=NOW)
    assert out["responses"], out["trace"]
    r = out["responses"][0]
    assert r["agent"] == "FloodLens" and r["verification_status"] == "predicted" and r["is_simulated"] is False
    assert r["confidence"] == S.base_confidence and r["distance_m"] <= 100 + S.grid_spacing_m
    kinds = {e["type"] for e in r["evidence"]}
    assert {"model_estimate", "terrain", "rainfall_forecast"} <= kinds
    assert out["risk_map"]["features"] and out["agent"]["mode"] == "deterministic"


def test_scenario_output_is_flagged_simulated():
    class Pit:
        name = "pit"

        def elevations(self, pts):
            return [880.0 if abs(lat - 12.9177) < 0.0012 and abs(lon - 77.625) < 0.0012 else 900.0 for lat, lon in pts]
    out = agent(Pit(), Rain(0, 0)).run([ROUTE], Scenario(accum_6h_mm=70, peak_mm_h=35), NOW)
    assert out["responses"] and all(r["is_simulated"] for r in out["responses"])
    assert out["forecast"]["is_scenario"] is True and any(e["type"] == "scenario" for e in out["responses"][0]["evidence"])
    assert any(t["kind"] == "scenario" for t in out["trace"])


def test_forecast_down_reports_unavailable_instead_of_guessing():
    out = agent(Bowl(), BrokenRain()).run([ROUTE], now=NOW)
    assert out["responses"] == [] and out["forecast"]["available"] is False
    assert {"source": "broken forecast", "status": "unavailable", "error": "down"} in out["source_health"]
    assert any(t["kind"] == "error" for t in out["trace"])


def test_reports_expire_dedupe_and_validate():
    a = agent()
    r1, c1 = a.add_report(12.9177, 77.625, "u1", now=NOW)
    r2, c2 = a.add_report(12.91772, 77.62502, "u1", now=NOW)
    assert c1 and not c2 and r1.id == r2.id
    assert len(a.active_reports(NOW + timedelta(hours=5))) == 1 and a.active_reports(NOW + timedelta(hours=7)) == []
    for bad in [(0, 0), (95, 77.6), (28.6, 77.2)]:
        with pytest.raises(GpsError):
            a.add_report(*bad, "u", now=NOW)


def test_report_raises_risk_even_with_no_forecast_rain():
    a = agent(Flat(), Rain(0, 0))
    a.add_report(12.9177, 77.625, "u1", now=NOW)
    out = a.run([ROUTE], now=NOW)
    assert out["responses"] and out["responses"][0]["verification_status"] == "reported"
    assert any(e["type"] == "community_report" for e in out["responses"][0]["evidence"])


# llm agent -----------------------------------------------------------------------
class Pit:
    name = "pit"

    def elevations(self, pts):
        return [880.0 if abs(lat - 12.9177) < 0.0012 and abs(lon - 77.625) < 0.0012 else 900.0 for lat, lon in pts]


def tc(name, args, id="x"):
    return ToolCall(id, name, json.dumps(args))


def test_llm_agent_uses_tools_and_cannot_invent_areas():
    base = agent(Pit(), Rain(70, 35))
    def final_reply(msgs):
        tool_msgs = [json.loads(m["content"]) for m in msgs if m["role"] == "tool"]
        area = next(t for t in tool_msgs if "areas" in t)["areas"][0]["cluster_id"]
        return LLMReply(None, [tc("final_answer", {"findings": [{"cluster_id": area, "reasoning": "Low spot on the route.", "recommended_action": "Use the bypass."}], "summary": "One area may flood."}, "3")])
    llm = ScriptedLLM([LLMReply("start", [tc("get_rain_forecast", {}, "1")]),
                       LLMReply(None, [tc("assess_route_flood_risk", {"route_id": "r1"}, "2")]),
                       LLMReply(None, [tc("final_answer", {"findings": [{"cluster_id": "made-up", "reasoning": "x", "recommended_action": "y"}], "summary": "s"}, "bad")]),
                       final_reply])
    out = FloodLensLLMAgent(base, llm).run([ROUTE], now=NOW)
    assert out["agent"]["mode"] == "llm" and out["agent"]["summary"] == "One area may flood."
    r = out["responses"][0]
    assert r["recommended_action"] == "Use the bypass." and r["verification_status"] == "predicted"
    assert any(e["type"] == "agent_reasoning" for e in r["evidence"])
    assert any(t["kind"] == "agent_tool_error" and "unknown cluster_id" in t["message"] for t in out["trace"])


def test_llm_agent_cannot_hide_an_at_risk_area():
    llm = ScriptedLLM([LLMReply(None, [tc("assess_route_flood_risk", {"route_id": "r1"}, "1")]),
                       LLMReply(None, [tc("final_answer", {"findings": [], "summary": "Nothing."}, "2")])])
    out = FloodLensLLMAgent(agent(Pit(), Rain(70, 35)), llm).run([ROUTE], now=NOW)
    assert out["responses"] and any(t["kind"] == "agent_policy" for t in out["trace"])


def test_llm_agent_must_assess_every_route_and_falls_back_on_failure():
    llm = ScriptedLLM([LLMReply(None, [tc("final_answer", {"findings": [], "summary": "done"}, "1")]),
                       LLMReply(None, [tc("assess_route_flood_risk", {"route_id": "r1"}, "2")]),
                       LLMReply(None, [tc("final_answer", {"findings": [], "summary": "ok"}, "3")])])
    out = FloodLensLLMAgent(agent(Pit(), Rain(70, 35)), llm).run([ROUTE], now=NOW)
    assert out["agent"]["mode"] == "llm" and any("not finished" in t["message"] for t in out["trace"])
    fb = FloodLensLLMAgent(agent(Pit(), Rain(70, 35)), ScriptedLLM([])).run([ROUTE], now=NOW)
    assert fb["agent"]["mode"] == "deterministic_fallback" and fb["responses"]


# api -----------------------------------------------------------------------------
def test_api():
    c = TestClient(create_app(agent(Pit(), Rain(70, 35)), llm=False))
    assert c.get("/health").json()["agent_mode"] == "deterministic"
    body = {"routes": [{"id": "r1", "name": "Commute", "geometry": [[77.615, 12.9177], [77.635, 12.9177]]}]}
    r = c.post("/investigate", json=body).json()
    assert r["responses"] and r["risk_map"]["type"] == "FeatureCollection"
    assert c.post("/reports", json={"lat": 12.9177, "lon": 77.625, "reporter_id": "u"}).status_code == 201
    assert c.post("/reports", json={"lat": 0, "lon": 0, "reporter_id": "u"}).status_code == 422
    assert len(c.get("/reports").json()) == 1
    sc = c.post("/investigate", json={**body, "use_preset_scenario": True}).json()
    assert sc["forecast"]["is_scenario"] is True
