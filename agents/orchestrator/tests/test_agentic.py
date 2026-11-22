import json

from agentkit import LLMReply, ScriptedLLM, ToolCall

from orchestrator.config import Settings
from orchestrator.graph import Orchestrator
from orchestrator.models import RunRequest
from orchestrator.store import Store
from test_orchestrator import T0, FakeRoad, FakeTrip, incident, plan, route, actions, reason


def tc(name, args, id="x"):
    return ToolCall(id, name, json.dumps(args))


def gather_script(rid="r1", road=True, trip=True):
    calls = []
    if trip:
        calls.append(tc("get_trip_prediction", {"route_id": rid}, "g1"))
    if road:
        calls.append(tc("check_road_incidents", {"route_id": rid}, "g2"))
    return [LLMReply("Check traffic then road.", calls[:1]), LLMReply(None, calls[1:]) if calls[1:] else LLMReply("ok"),
            LLMReply(None, [tc("final_answer", {"summary": "Checked everything."}, "g3")])]


def decisions(*items):
    return LLMReply(None, [tc("final_decisions", {"decisions": list(items)}, "d1")])


def make(llm, trip=None, road=None, settings=None):
    return Orchestrator(trip or FakeTrip(plan(alt_predicted=2500)), road or FakeRoad([incident("i1", sev="moderate", d=10)]),
                        Store(), settings or Settings(), lambda: T0, llm=llm)


def run(o, **kw):
    return o.run(RunRequest(routes=[route()], **kw))


def test_agent_gathers_reviews_and_explains():
    llm = ScriptedLLM(gather_script() + [decisions(
        {"key": "traffic:r1", "action": "alert", "reason": "Large gap to the departure estimate.", "message": "Traffic will build on your commute; the other road is faster."},
        {"key": "road:i1", "action": "alert", "reason": "Close to route."})])
    r = run(make(llm))
    assert r["summary"]["mode"] == "llm" and r["summary"]["model"] == "scripted"
    assert actions(r) == {"traffic:r1": "alert", "road:i1": "alert"}
    traffic = next(d for d in r["decisions"] if d["key"] == "traffic:r1")
    assert traffic["finding"]["explanation"].startswith("Traffic will build")
    assert any(x.startswith("agent:") for x in traffic["reasons"])
    msgs = [e["message"] for e in r["events"] if e["node"] == "agent_gather"]
    assert any("[tool_call] Calling get_trip_prediction" in m for m in msgs) and any("Agent summary" in m for m in msgs)
    assert [e["node"] for e in r["events"]].count("agent_review") >= 1


def test_gather_cannot_finish_before_covering_every_route_and_category():
    llm = ScriptedLLM([LLMReply(None, [tc("final_answer", {"summary": "done"}, "1")])] + gather_script() +
                      [decisions({"key": "traffic:r1", "action": "alert", "reason": "r"}, {"key": "road:i1", "action": "alert", "reason": "r"})])
    r = run(make(llm))
    assert r["summary"]["mode"] == "llm"
    assert any("tool_error" in e["message"] and "still need" in e["message"] for e in r["events"])


def test_agent_can_suppress_minor_but_never_high_severity():
    road = FakeRoad([incident("i1", sev="moderate", d=10), incident("i2", sev="high", d=10, lat=12.9, lon=77.63)])
    llm = ScriptedLLM(gather_script() + [decisions(
        {"key": "traffic:r1", "action": "suppress", "reason": "Not worth interrupting."},
        {"key": "road:i1", "action": "suppress", "reason": "Minor."},
        {"key": "road:i2", "action": "suppress", "reason": "Ignore."})])
    r = run(make(llm, road=road))
    a = actions(r)
    assert a["road:i1"] == "suppress" and "agent judgment" in reason(r, "road:i1")
    assert a["road:i2"] == "alert"                                  # high severity: policy overrides the model
    d = next(d for d in r["decisions"] if d["key"] == "road:i2")
    assert any("always alert" in x for x in d["reasons"])


def test_policy_beats_the_model_for_simulated_data():
    road = FakeRoad([incident("i1", sev="critical", sim=True)])
    llm = ScriptedLLM(gather_script() + [decisions({"key": "road:i1", "action": "alert", "reason": "Looks important", "message": "Alert!"})])
    r = Orchestrator(FakeTrip(), road, Store(), Settings(), lambda: T0, llm=llm).run(RunRequest(routes=[route(categories=["road"])]))
    assert actions(r) == {"road:i1": "suppress"} and "simulated" in reason(r, "road:i1")


def test_review_must_cover_real_keys():
    llm = ScriptedLLM(gather_script() + [
        decisions({"key": "made-up", "action": "alert", "reason": "x"}),
        decisions({"key": "road:i1", "action": "alert", "reason": "ok"})])
    r = Orchestrator(FakeTrip(), FakeRoad([incident("i1")]), Store(), Settings(), lambda: T0, llm=llm).run(RunRequest(routes=[route(categories=["road"])]))
    assert actions(r) == {"road:i1": "alert"}
    assert any("unknown keys" in e["message"] for e in r["events"])


def test_model_failure_in_gather_falls_back_to_fixed_checks():
    r = run(make(ScriptedLLM([])))
    assert r["summary"]["mode"] == "deterministic_fallback"
    assert actions(r)["road:i1"] == "alert" and actions(r)["traffic:r1"] == "alert"
    assert any("using the fixed checks" in e["message"] for e in r["events"])


def test_model_failure_in_review_uses_policy_decisions():
    r = run(make(ScriptedLLM(gather_script())))     # script ends before review
    assert r["summary"]["mode"] == "llm"
    assert actions(r)["road:i1"] == "alert"
    assert any("using policy decisions only" in e["message"] for e in r["events"])


def test_tripcast_down_is_reported_to_the_model_and_run_continues():
    r0 = route(categories=["road"]).model_copy(update={"geometry": [(77.6, 12.9), (77.65, 12.9)]})
    llm = ScriptedLLM(gather_script() + [decisions({"key": "road:i1", "action": "alert", "reason": "ok"})])
    res = Orchestrator(FakeTrip(fail=True), FakeRoad([incident("i1")]), Store(), Settings(), lambda: T0, llm=llm).run(RunRequest(routes=[r0]))
    assert res["summary"]["mode"] == "llm" and actions(res) == {"road:i1": "alert"}
    assert "TripCast" in res["summary"]["headline"]
