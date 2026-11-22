"""LLM-driven nodes for the orchestrator graph.

gather: the model decides which tools to call (trip prediction, road incidents per route) and may react to
failures; a guardrail makes it cover every monitored route and category before it can finish.
review: the model sees the deterministic scores and may suggest suppressing low-importance findings and
write a plain-language explanation. It never sets scores, severity or distances. The policy layer in
`decide` has the final word: high/critical findings always alert, and every rule (thresholds, cooldown,
preferences, cap) still applies.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from agentkit import Tool, run_agent
from pydantic import BaseModel, Field

from .clients import AgentUnavailable
from .models import Finding

if TYPE_CHECKING:
    from .graph import Orchestrator, State

GATHER_SYSTEM = """You are the NammaPulse orchestrator. Your job is to check each monitored route for things that
could affect the traveller: traffic that will build while they travel (TripCast) and road incidents on the
route (RoadTrust).

Process: for every route call get_trip_prediction (if traffic monitoring is enabled for it) and
check_road_incidents (if road monitoring is enabled), then call final_answer with a one-sentence summary.
If a tool reports that an agent is unavailable, say so in your summary; do not guess its results.
Facts come only from tool results. Do not invent numbers."""

REVIEW_SYSTEM = """You are the NammaPulse orchestrator reviewing scored findings before alerts are sent.
Each finding already has a deterministic relevance score; you cannot change scores, severity or distances.

For each finding decide 'alert' or 'suppress' and give a short plain reason. Suppress only things that are
clearly not worth interrupting the traveller for. Never suppress high or critical severity. For findings you
alert on, write 'message': one or two plain sentences for the traveller, using only facts from the finding.
You may call get_alert_history to see whether a finding was alerted recently. Finish with final_decisions
covering every finding key."""


class RouteArg(BaseModel):
    route_id: str


class SummaryArg(BaseModel):
    summary: str = Field(max_length=500)


class KeyArg(BaseModel):
    key: str


class Judgment(BaseModel):
    key: str
    action: Literal["alert", "suppress"]
    reason: str = Field(max_length=300)
    message: str | None = Field(default=None, max_length=400)


class DecisionsArg(BaseModel):
    decisions: list[Judgment]


def _m(s: float) -> int:
    return round(s / 60)


def run_gather(o: "Orchestrator", st: "State") -> dict:
    req = st["request"]
    routes = {r.id: r for r in req.routes}
    trips: dict[str, dict] = {}
    geoms: dict[str, list] = {}
    road_responses: list[dict] = []
    road_health: list[dict] = []
    called: set[tuple[str, str]] = set()
    degraded: list[str] = []

    def route_of(rid: str):
        if rid not in routes:
            raise ValueError(f"unknown route_id '{rid}'. Known: {sorted(routes)}")
        return routes[rid]

    def trip(a: RouteArg):
        r = route_of(a.route_id)
        called.add(("trip", r.id))
        try:
            entry = o._trip_one(r, req.depart_at)
        except (AgentUnavailable, KeyError, ValueError) as exc:
            degraded.append(f"TripCast ({r.id})")
            if r.geometry:
                geoms[r.id] = [tuple(c) for c in r.geometry]
            return {"error": f"TripCast unavailable: {exc}", "fallback_geometry": bool(r.geometry)}
        trips[r.id] = entry
        geoms[r.id] = [tuple(c) for c in entry["primary"]["geometry"]]
        p = entry["primary"]["prediction"]
        alts = [{"via": x["via"], "predicted_min": _m(x["prediction"]["predicted_s"]),
                 "saves_min": _m(p["predicted_s"] - x["prediction"]["predicted_s"]),
                 "has_closure": any(w["kind"] == "closure" for w in x.get("warnings", []))}
                for x in entry["plan"]["routes"] if x["id"] != entry["primary"]["id"]]
        return {"predicted_min": _m(p["predicted_s"]), "departure_estimate_min": _m(p["snapshot_s"]),
                "free_flow_min": _m(p["free_flow_s"]), "basis": p["basis"], "alternatives": alts}

    def road(a: RouteArg):
        r = route_of(a.route_id)
        called.add(("road", r.id))
        if r.id not in geoms:
            return {"error": "no route geometry available (call get_trip_prediction first, or TripCast is down)"}
        try:
            resp = o.road.investigate([{"id": r.id, "geometry": geoms[r.id], "corridor_m": r.corridor_m}])
        except (AgentUnavailable, KeyError) as exc:
            degraded.append("RoadTrust")
            return {"error": f"RoadTrust unavailable: {exc}"}
        road_responses.extend(resp.get("responses", []))
        road_health.extend(resp.get("source_health", []))
        for h in resp.get("source_health", []):
            if h.get("status") != "ok":
                degraded.append(f"RoadTrust source: {h['source']}")
        return {"incidents": [{"incident_id": w["incident_id"], "kind": w["incident_type"], "severity": w["severity"],
                               "distance_m": w.get("distance_m"), "verification": w["verification_status"],
                               "simulated": w.get("is_simulated", False)} for w in resp.get("responses", [])],
                "source_health": resp.get("source_health", [])}

    def final(a: SummaryArg):
        missing = []
        for r in req.routes:
            if "traffic" in r.categories and ("trip", r.id) not in called:
                missing.append(f"get_trip_prediction({r.id})")
            if "road" in r.categories and ("road", r.id) not in called:
                missing.append(f"check_road_incidents({r.id})")
        if missing:
            raise ValueError("not finished: still need " + ", ".join(missing))
        return a

    tools = [Tool("get_trip_prediction", "Predicted travel time, departure-time estimate and alternative roads for a route.", RouteArg, trip),
             Tool("check_road_incidents", "Road incidents (potholes, closures, construction) inside a route's corridor.", RouteArg, road),
             Tool("final_answer", "Finish with a one-sentence summary once every route is checked.", SummaryArg, final, terminal=True)]
    task = "Monitored routes:\n" + "\n".join(
        f"- {r.id} ({r.name or 'unnamed'}): traffic={'on' if 'traffic' in r.categories else 'off'}, road={'on' if 'road' in r.categories else 'off'}"
        for r in req.routes)
    events: list[dict] = []
    res = run_agent(o.llm, GATHER_SYSTEM, task, tools, emit=lambda k, m, d: events.append(
        {"node": "agent_gather", "level": "warn" if k in ("error", "tool_error") else "info", "message": f"[{k}] {m}", "data": d}))
    if not res.ok:
        events.append({"node": "agent_gather", "level": "warn", "data": {},
                       "message": f"Model did not finish ({res.error}); using the fixed checks instead"})
        fb = {**st, "events": []}
        t = o.n_trip(fb)
        fb.update({k: v for k, v in t.items() if k != "events"})
        r_ = o.n_road(fb)
        return {"trips": t["trips"], "geometries": t["geometries"], "road": r_.get("road", {}),
                "degraded": r_.get("degraded", t["degraded"]), "mode": "deterministic_fallback",
                "events": events + t["events"] + r_["events"]}
    events.append({"node": "agent_gather", "level": "info", "data": {"model": o.llm.model, "steps": res.steps},
                   "message": f"Agent summary: {res.final.summary}"})
    return {"trips": trips, "geometries": geoms, "road": {"responses": road_responses, "source_health": road_health},
            "degraded": list(dict.fromkeys(degraded)), "mode": "llm", "events": events}


def run_review(o: "Orchestrator", st: "State") -> dict:
    findings: list[Finding] = st["findings"]
    if not findings:
        return {"judgments": {}, "events": []}
    keys = {f.key for f in findings}

    def history(a: KeyArg):
        if a.key not in keys:
            raise ValueError(f"unknown key '{a.key}'")
        last = o.store.last_alert(a.key)
        return {"last_alert": {"severity": last[0], "at": last[1].isoformat()} if last else None}

    def final(a: DecisionsArg):
        got = {d.key for d in a.decisions}
        if got - keys:
            raise ValueError(f"unknown keys: {sorted(got - keys)}")
        if keys - got:
            raise ValueError(f"missing decisions for: {sorted(keys - got)}")
        return a

    tools = [Tool("get_alert_history", "When a finding was last alerted, and at what severity.", KeyArg, history),
             Tool("final_decisions", "Finish: one decision for every finding key.", DecisionsArg, final, terminal=True)]
    task = "Findings (scores are final):\n" + "\n".join(
        f"- key={f.key} | {f.title} | severity={f.severity} | basis={f.basis} | relevance={f.score} | "
        f"{'simulated demo data' if f.simulated else 'real'} | suggested action: {f.action}" for f in findings)
    events: list[dict] = []
    res = run_agent(o.llm, REVIEW_SYSTEM, task, tools, emit=lambda k, m, d: events.append(
        {"node": "agent_review", "level": "warn" if k in ("error", "tool_error") else "info", "message": f"[{k}] {m}", "data": d}))
    if not res.ok:
        events.append({"node": "agent_review", "level": "warn", "data": {},
                       "message": f"Model did not finish ({res.error}); using policy decisions only"})
        return {"judgments": {}, "events": events}
    return {"judgments": {d.key: d.model_dump() for d in res.final.decisions}, "events": events}
