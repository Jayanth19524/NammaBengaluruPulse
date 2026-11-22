from __future__ import annotations

from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from .agent import FloodLensAgent, GpsError, city_bbox
from .config import load_settings
from .models import Route, Scenario
from .sources import OpenMeteoElevation, OpenMeteoRain


class InvestigateRequest(BaseModel):
    routes: list[Route]
    scenario: Scenario | None = None
    use_preset_scenario: bool = False   # shortcut for the configured "what-if heavy rain"


class ReportRequest(BaseModel):
    lat: float
    lon: float
    reporter_id: str
    depth_cm: float | None = None
    note: str = ""


def create_app(agent: FloodLensAgent | None = None, llm=None) -> FastAPI:
    if agent is None:
        s = load_settings()
        agent = FloodLensAgent(s, OpenMeteoElevation(), OpenMeteoRain(), city_bbox())
    if llm is None:
        try:
            from agentkit import from_env
            llm = from_env()  # None without a configured key -> deterministic model only
        except ImportError:
            llm = None
    investigator = None
    if llm:
        from .llm_agent import FloodLensLLMAgent
        investigator = FloodLensLLMAgent(agent, llm)
    app = FastAPI(title="FloodLens")

    @app.get("/health")
    def health():
        return {"agent": "FloodLens", "agent_mode": "llm" if llm else "deterministic", "model": getattr(llm, "model", None),
                "sources": [agent.elevation.name, agent.rain.name], "active_reports": len(agent.active_reports(datetime.now(timezone.utc)))}

    @app.post("/investigate")
    def investigate(req: InvestigateRequest):
        scenario = req.scenario or (Scenario(accum_6h_mm=agent.s.scenario_accum6_mm, peak_mm_h=agent.s.scenario_peak_mm_h)
                                    if req.use_preset_scenario else None)
        try:
            return (investigator or agent).run(req.routes, scenario)
        except (ValueError, ZeroDivisionError) as exc:
            raise HTTPException(422, str(exc))

    @app.post("/reports", status_code=201)
    def report(req: ReportRequest):
        try:
            rep, created = agent.add_report(req.lat, req.lon, req.reporter_id, req.depth_cm, req.note)
        except GpsError as exc:
            raise HTTPException(422, str(exc))
        return {"id": rep.id, "created": created, "at": rep.at.isoformat(), "status": "reported, not verified"}

    @app.get("/reports")
    def reports():
        now = datetime.now(timezone.utc)
        return [{"id": r.id, "lat": r.lat, "lon": r.lon, "at": r.at.isoformat(), "depth_cm": r.depth_cm, "note": r.note}
                for r in agent.active_reports(now)]

    return app
