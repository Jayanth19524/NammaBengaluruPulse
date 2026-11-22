import json
from datetime import datetime, timezone

from agentkit import LLMReply, ScriptedLLM, ToolCall

from roadtrust.adapters.mock import MockRoadAdapter
from roadtrust.agent import RoadTrustAgent
from roadtrust.config import load_city
from roadtrust.detector import NullDetector
from roadtrust.llm_agent import RoadTrustLLMAgent
from roadtrust.models import Route
from roadtrust.store import InMemoryStore

NOW = datetime(2026, 11, 22, 12, 0, tzinfo=timezone.utc)
CITY = load_city()
ROUTE = Route(id="r1", name="Demo", geometry=[(77.60, 12.9177), (77.65, 12.9177)])


def tc(name, args, id="x"):
    return ToolCall(id, name, json.dumps(args))


def make(adapters=None):
    s = CITY.roadtrust
    base = RoadTrustAgent(CITY, InMemoryStore(s.dedup_radius_m, s.stale_after_days), NullDetector(), adapters or [])
    return base


def seed(base):
    near, _, _ = base.submit_report(reporter="u1", latitude=12.91775, longitude=77.62, user_severity="high", now=NOW)
    far, _, _ = base.submit_report(reporter="u2", latitude=12.9300, longitude=77.62, now=NOW)  # ~1.4 km off
    return near, far


def final(findings, summary="done"):
    return LLMReply(None, [tc("final_answer", {"findings": findings, "summary": summary}, "f")])


def test_agent_investigates_with_tools_and_enriches_findings():
    base = make()
    near, far = seed(base)
    llm = ScriptedLLM([
        LLMReply("Check the area", [tc("list_active_incidents", {}, "1")]),
        LLMReply(None, [tc("check_route_corridor", {"route_id": "r1", "incident_id": near.id}, "2"),
                        tc("check_route_corridor", {"route_id": "r1", "incident_id": far.id}, "3")]),
        final([{"incident_id": near.id, "route_id": "r1", "reasoning": "Reported pothole 5 m from route.",
                "recommended_action": "Take the service lane."}], "One issue on the route."),
    ])
    out = RoadTrustLLMAgent(base, llm).investigate([ROUTE], NOW)
    assert out["agent"]["mode"] == "llm" and out["agent"]["summary"] == "One issue on the route."
    assert [t["tool"] for t in out["agent"]["tool_calls"]] == ["list_active_incidents", "check_route_corridor", "check_route_corridor", "final_answer"]
    assert len(out["responses"]) == 1
    r = out["responses"][0]
    assert r.incident_id == near.id and r.recommended_action == "Take the service lane."
    assert r.verification_status == "reported" and r.distance_m < 50          # facts from the store, not the model
    assert any(e["type"] == "agent_reasoning" for e in r.evidence)


def test_model_cannot_report_unchecked_or_out_of_corridor_incident():
    base = make()
    near, far = seed(base)
    llm = ScriptedLLM([
        LLMReply(None, [tc("final_answer", {"findings": [{"incident_id": near.id, "route_id": "r1", "reasoning": "x", "recommended_action": "y"}], "summary": "s"}, "1")]),
        LLMReply(None, [tc("check_route_corridor", {"route_id": "r1", "incident_id": far.id}, "2")]),
        LLMReply(None, [tc("final_answer", {"findings": [{"incident_id": far.id, "route_id": "r1", "reasoning": "x", "recommended_action": "y"}], "summary": "s"}, "3")]),
        LLMReply(None, [tc("check_route_corridor", {"route_id": "r1", "incident_id": near.id}, "4")]),
        final([{"incident_id": near.id, "route_id": "r1", "reasoning": "ok", "recommended_action": "Slow down"}]),
    ])
    out = RoadTrustLLMAgent(base, llm).investigate([ROUTE], NOW)
    errors = [json.loads(m["content"])["error"] for call in llm.calls[1:] for m in call if m["role"] == "tool" and "error" in m["content"]]
    assert any("before reporting" in e for e in errors) and any("outside the corridor" in e for e in errors)
    assert [r.incident_id for r in out["responses"]] == [near.id]


def test_incident_the_model_skips_is_still_reported():
    base = make()
    near, _ = seed(base)
    llm = ScriptedLLM([final([], "Nothing to report.")])
    out = RoadTrustLLMAgent(base, llm).investigate([ROUTE], NOW)
    assert [r.incident_id for r in out["responses"]] == [near.id]       # the model cannot hide it
    assert "did not assess" in out["responses"][0].evidence[-1]["text"]


def test_fetch_source_data_runs_adapters_and_feeds_investigation():
    base = make([MockRoadAdapter()])
    llm = ScriptedLLM([LLMReply(None, [tc("fetch_source_data", {"route_id": "r1"}, "1")]),
                       LLMReply(None, [tc("list_active_incidents", {}, "2")]),
                       lambda msgs: LLMReply(None, [tc("check_route_corridor", {"route_id": "r1", "incident_id": json.loads(msgs[-1]["content"])[0]["incident_id"]}, "3")]),
                       lambda msgs: final([{"incident_id": base.store.active(NOW)[0].id, "route_id": "r1", "reasoning": "Demo pothole", "recommended_action": "Slow down"}])])
    out = RoadTrustLLMAgent(base, llm).investigate([ROUTE], NOW)
    assert out["source_health"][0]["simulated"] is True
    assert out["responses"][0].is_simulated is True


def test_falls_back_to_deterministic_when_model_fails():
    base = make()
    near, _ = seed(base)
    out = RoadTrustLLMAgent(base, ScriptedLLM([])).investigate([ROUTE], NOW)
    assert out["agent"]["mode"] == "deterministic_fallback" and "script exhausted" in out["agent"]["reason"]
    assert [r.incident_id for r in out["responses"]] == [near.id]


def test_unknown_route_is_rejected_to_the_model():
    base = make()
    llm = ScriptedLLM([LLMReply(None, [tc("fetch_source_data", {"route_id": "nope"}, "1")]), final([])])
    out = RoadTrustLLMAgent(base, llm).investigate([ROUTE], NOW)
    err = json.loads([m for m in llm.calls[1] if m["role"] == "tool"][0]["content"])["error"]
    assert "unknown route_id" in err and out["agent"]["mode"] == "llm"
