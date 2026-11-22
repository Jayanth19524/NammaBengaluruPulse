"""RoadTrust as a tool-using LLM agent.

The model decides which tools to call (fetch source data, list incidents, check a route corridor, read
details) and writes the reasoning and advice. It cannot invent facts: distances, severity, confidence and
verification status come from the tools / store; it can only report an incident it has checked against the
route's corridor; and any in-corridor incident it fails to mention is still included. If the model is
unavailable or does not conclude, the deterministic investigation runs instead and the response says so.
"""
from __future__ import annotations

from datetime import datetime, timezone

from agentkit import LLMClient, Tool, run_agent
from pydantic import BaseModel, Field

from .adapters.base import AdapterError
from .agent import ACTIONS, RoadTrustAgent, _dedupe_health
from .geo import distance_to_route_m, route_bbox
from .models import Route

SYSTEM = """You are RoadTrust, the road-infrastructure agent in NammaPulse. You watch for road damage, closures
and construction that affect a user's monitored routes.

Work like an investigator:
1. Call fetch_source_data for each route to refresh data from public sources.
2. Call list_active_incidents, then call check_route_corridor for each incident that could be near a route.
3. Call get_incident_details for anything that needs a closer look (evidence, reports, repair claims).
4. Finish by calling final_answer.

Rules you must follow:
- Facts come from tools only. Never invent incidents, distances, severities or verification status.
- User reports are 'reported', not verified. Never describe them as confirmed.
- Never claim a repair is confirmed unless a tool shows an official repair.
- Simulated (demo) data must be described as demo data.
- In final_answer, include only incidents you checked and found inside the corridor, with a short reasoning
  and one practical recommended_action for the traveller. Be specific and plain; no jargon."""


class RouteArg(BaseModel):
    route_id: str


class NoArgs(BaseModel):
    pass


class CheckArg(BaseModel):
    route_id: str
    incident_id: str


class IncidentArg(BaseModel):
    incident_id: str


class FindingArg(BaseModel):
    incident_id: str
    route_id: str
    reasoning: str = Field(max_length=600)
    recommended_action: str = Field(max_length=240)


class FinalArg(BaseModel):
    findings: list[FindingArg]
    summary: str = Field(max_length=500)


class RoadTrustLLMAgent:
    def __init__(self, base: RoadTrustAgent, llm: LLMClient):
        self.base, self.llm = base, llm

    def investigate(self, routes: list[Route], now: datetime | None = None) -> dict:
        now = now or datetime.now(timezone.utc)
        b = self.base
        b.log.start(len(routes))
        by_id = {r.id: r for r in routes}
        checked: dict[tuple[str, str], float] = {}
        health: list[dict] = []

        def corridor(r: Route) -> float:
            return r.corridor_m or b.city.roadtrust.default_corridor_m

        def route_of(rid: str) -> Route:
            if rid not in by_id:
                raise ValueError(f"unknown route_id '{rid}'. Known: {sorted(by_id)}")
            return by_id[rid]

        def fetch(a: RouteArg):
            r = route_of(a.route_id)
            bbox = route_bbox(r.geometry, corridor(r))
            out = []
            for ad in b.adapters:
                try:
                    recs = ad.fetch(bbox, now)
                    for rep in recs:
                        b.store.ingest(rep)
                    health.append({"source": ad.name, "status": "ok", "simulated": ad.is_simulated})
                    out.append({"source": ad.name, "status": "ok", "records": len(recs), "simulated": ad.is_simulated})
                except AdapterError as exc:
                    health.append({"source": ad.name, "status": "degraded", "error": str(exc)})
                    out.append({"source": ad.name, "status": "unavailable", "error": str(exc)})
            return out or [{"note": "no external sources configured"}]

        def list_active(_: NoArgs):
            return [{"incident_id": i.id, "kind": i.kind, "lat": i.latitude, "lon": i.longitude, "severity": i.severity,
                     "verification": i.verification_status, "reports": i.report_count, "repair_status": i.repair_status,
                     "hours_since_seen": round((now - i.last_seen).total_seconds() / 3600, 1), "simulated": i.is_simulated}
                    for i in b.store.active(now)]

        def check(a: CheckArg):
            r, inc = route_of(a.route_id), b.store.get(a.incident_id)
            if inc is None:
                raise ValueError(f"unknown incident_id '{a.incident_id}'")
            d = distance_to_route_m(inc.latitude, inc.longitude, r.geometry)
            checked[(inc.id, r.id)] = d
            return {"distance_m": round(d, 1), "corridor_m": corridor(r), "within_corridor": d <= corridor(r)}

        def details(a: IncidentArg):
            inc = b.store.get(a.incident_id)
            if inc is None:
                raise ValueError(f"unknown incident_id '{a.incident_id}'")
            return {"kind": inc.kind, "severity": inc.severity, "verification": inc.verification_status,
                    "description": inc.description, "reports": inc.report_count, "sources": inc.sources,
                    "repair_status": inc.repair_status, "simulated": inc.is_simulated, "confidence": inc.confidence,
                    "evidence_types": [e.get("type") for e in inc.evidence]}

        def final(a: FinalArg):
            for f in a.findings:
                route_of(f.route_id)
                d = checked.get((f.incident_id, f.route_id))
                if d is None:
                    raise ValueError(f"call check_route_corridor for incident {f.incident_id} on {f.route_id} before reporting it")
                if d > corridor(by_id[f.route_id]):
                    raise ValueError(f"incident {f.incident_id} is outside the corridor of {f.route_id} ({round(d)} m); do not report it")
            return a

        tools = [
            Tool("fetch_source_data", "Refresh road incidents (closures, construction) from public sources for one route's area.", RouteArg, fetch),
            Tool("list_active_incidents", "List all currently active road incidents RoadTrust knows about.", NoArgs, list_active),
            Tool("check_route_corridor", "Compute the real distance from one incident to one route and whether it is inside the route's corridor.", CheckArg, check),
            Tool("get_incident_details", "Evidence, report count, sources and repair status for one incident.", IncidentArg, details),
            Tool("final_answer", "Finish. Report the incidents (already checked and inside a corridor) with reasoning and advice.", FinalArg, final, terminal=True),
        ]
        task = ("Monitored routes:\n" + "\n".join(f"- {r.id} ({r.name or 'unnamed'}), corridor {corridor(r):.0f} m" for r in routes)
                + "\nInvestigate and report what affects these routes.")

        def emit(kind: str, message: str, data: dict) -> None:
            b.log._emit(f"agent_{kind}", message, data)

        res = run_agent(self.llm, SYSTEM, task, tools, emit=emit)
        if not res.ok:
            b.log._emit("agent_error", f"LLM agent did not conclude ({res.error}); using the deterministic check instead.", {})
            out = b.investigate(routes, now)
            out["agent"] = {"mode": "deterministic_fallback", "reason": res.error, "model": getattr(self.llm, "model", "")}
            return out

        notes = {(f.incident_id, f.route_id): f for f in res.final.findings}
        responses, omitted = [], 0
        for r in routes:
            # Completeness is enforced here, not by the model: every in-corridor incident is reported.
            for inc in b.store.active(now):
                d = distance_to_route_m(inc.latitude, inc.longitude, r.geometry)
                if d > corridor(r):
                    continue
                resp = b._to_response(inc, r.id, d)
                note = notes.get((inc.id, r.id))
                if note:
                    resp.recommended_action = note.recommended_action.strip() or ACTIONS[inc.kind]
                    resp.evidence.append({"type": "agent_reasoning", "model": getattr(self.llm, "model", ""), "text": note.reasoning})
                else:
                    omitted += 1
                    resp.evidence.append({"type": "agent_reasoning", "text": "Included by policy; the agent did not assess this incident."})
                responses.append(resp)
        if omitted:
            b.log._emit("agent_policy", f"{omitted} in-corridor incident(s) were not assessed by the model and were included anyway.", {})
        order = ["info", "low", "moderate", "high", "critical"]
        responses.sort(key=lambda x: (-order.index(x.severity), x.distance_m or 0))
        b.log.result(len(responses))
        b.log.done()
        return {"responses": responses, "source_health": _dedupe_health(health),
                "audit": {"routes": len(routes), "active_incidents": len(b.store.active(now)), "relevant": len(responses), "at": now.isoformat()},
                "agent": {"mode": "llm", "model": getattr(self.llm, "model", ""), "steps": res.steps,
                          "tool_calls": res.tool_calls, "summary": res.final.summary}}
