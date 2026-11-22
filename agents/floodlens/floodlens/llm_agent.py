"""FloodLens as a tool-using LLM agent. The model chooses which tools to call and writes the reasoning and
advice; risk scores, areas, distances and severities come only from the deterministic model. It can report only
areas the model assessed for a route, and any assessed at-risk area it omits is still reported. If the model
fails, the deterministic result is returned and says so."""
from __future__ import annotations

from datetime import datetime, timezone

from agentkit import LLMClient, Tool, run_agent
from pydantic import BaseModel, Field

from .agent import FloodLensAgent
from .models import Route, Scenario

SYSTEM = """You are FloodLens, the flood-risk agent in NammaPulse. You predict where flooding or waterlogging is
likely to affect a traveller's monitored routes, using a terrain-and-rainfall model that you call as tools.

Process: call get_rain_forecast; call assess_route_flood_risk for every route; call list_flood_reports if useful;
then finish with final_answer.

Rules:
- Facts and numbers come from tool results only. Never invent risk values, places or rainfall.
- Everything the model produces is an ESTIMATE, not a measurement. Rainfall alone does not cause flooding; the
  model combines it with low-lying terrain. Say 'may' or 'likely', never 'will flood'.
- If the forecast shows little rain, say there is no significant flood risk expected. Do not alarm.
- A what-if scenario is not a forecast; if the tool says is_scenario, say so.
- Community reports are 'reported', not verified.
- In final_answer include only areas returned by assess_route_flood_risk, with brief reasoning and one practical action."""


class NoArgs(BaseModel):
    pass


class RouteArg(BaseModel):
    route_id: str


class FindingArg(BaseModel):
    cluster_id: str
    reasoning: str = Field(max_length=500)
    recommended_action: str = Field(max_length=240)


class FinalArg(BaseModel):
    findings: list[FindingArg]
    summary: str = Field(max_length=500)


class FloodLensLLMAgent:
    def __init__(self, base: FloodLensAgent, llm: LLMClient):
        self.base, self.llm = base, llm

    def run(self, routes: list[Route], scenario: Scenario | None = None, now: datetime | None = None) -> dict:
        now = now or datetime.now(timezone.utc)
        a = self.base.analysis(routes, scenario, now)
        by_id = {r.id: r for r in routes}
        assessed: dict[str, object] = {}

        def forecast(_: NoArgs):
            return a.summary()

        def assess(x: RouteArg):
            if x.route_id not in by_id:
                raise ValueError(f"unknown route_id '{x.route_id}'. Known: {sorted(by_id)}")
            cl = a.clusters(by_id[x.route_id])
            for c in cl:
                assessed[c.id] = c
            return {"route_id": x.route_id, "is_scenario": bool(scenario), "areas": [
                {"cluster_id": c.id, "risk": c.risk, "severity": c.severity, "distance_from_route_m": c.distance_m,
                 "relief_m": c.relief_m, "elevation_m": c.elevation_m, "cells": c.n_cells, "community_reported": c.reported} for c in cl]}

        def reports(_: NoArgs):
            return [{"lat": r.lat, "lon": r.lon, "hours_ago": round((now - r.at).total_seconds() / 3600, 1), "depth_cm": r.depth_cm}
                    for r in self.base.active_reports(now)]

        def final(f: FinalArg):
            missing = [r.id for r in routes if r.id not in a.assessed]
            if missing:
                raise ValueError(f"not finished: call assess_route_flood_risk for {missing}")
            for item in f.findings:
                if item.cluster_id not in assessed:
                    raise ValueError(f"unknown cluster_id '{item.cluster_id}'; use ids returned by assess_route_flood_risk")
            return f

        tools = [Tool("get_rain_forecast", "Rainfall forecast summary for the monitored area (peak mm/h, worst 6 h total, timing).", NoArgs, forecast),
                 Tool("assess_route_flood_risk", "Run the flood-risk model for one route: areas near it that may flood, with deterministic risk scores.", RouteArg, assess),
                 Tool("list_flood_reports", "Recent community waterlogging reports (unverified).", NoArgs, reports),
                 Tool("final_answer", "Finish: report the assessed areas with reasoning and one action each.", FinalArg, final, terminal=True)]
        task = "Monitored routes:\n" + "\n".join(f"- {r.id} ({r.name or 'unnamed'})" for r in routes) + \
               ("\nNote: rainfall is a what-if scenario, not a forecast." if scenario else "")
        res = run_agent(self.llm, SYSTEM, task, tools, emit=lambda k, m, d: a.trace(f"agent_{k}", m, d))
        if not res.ok:
            a.trace("agent_error", f"LLM agent did not conclude ({res.error}); using the deterministic result.")
            for r in routes:
                a.clusters(r)
            return a.result([c for r in routes for c in a.assessed[r.id]], {},
                            {"mode": "deterministic_fallback", "reason": res.error, "model": getattr(self.llm, "model", "")})
        notes = {i.cluster_id: {"reasoning": i.reasoning, "recommended_action": i.recommended_action, "model": getattr(self.llm, "model", "")}
                 for i in res.final.findings}
        clusters = [c for r in routes for c in a.assessed[r.id]]
        omitted = sum(c.id not in notes for c in clusters)
        if omitted:
            a.trace("agent_policy", f"{omitted} at-risk area(s) were not assessed in the model's answer and were included anyway.")
        return a.result(clusters, notes, {"mode": "llm", "model": getattr(self.llm, "model", ""), "steps": res.steps,
                                          "tool_calls": res.tool_calls, "summary": res.final.summary})
