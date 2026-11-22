from __future__ import annotations

import os
from datetime import datetime

from fastapi import FastAPI, HTTPException

from .live import TomTomLive
from .models import PlanRequest
from .planner import Planner, RoadIncidents
from .predictor import Predictor
from .profile import CongestionProfile
from .routing import OsrmRouter, RoutingError


def create_app(planner: Planner | None = None) -> FastAPI:
    if planner is None:
        key = os.environ.get("TOMTOM_API_KEY")
        predictor = Predictor(CongestionProfile(), TomTomLive(key) if key else None)
        rt = os.environ.get("ROADTRUST_URL", "http://localhost:8002")
        planner = Planner(OsrmRouter(), predictor, RoadIncidents(rt))
    app = FastAPI(title="TripCast")

    @app.get("/health")
    def health():
        p = planner.predictor
        return {"agent": "TripCast", "profile": p.profile.source,
                "live_traffic": p.live.name if p.live else None, "road_incidents": planner.incidents is not None}

    @app.post("/plan")
    def plan(req: PlanRequest):
        try:
            out = planner.plan(req.origin, req.destination, req.depart_at, req.check_incidents)
        except RoutingError as exc:
            raise HTTPException(502, str(exc))
        return {**out, "routes": [r.model_dump(mode="json") for r in out["routes"]],
                "departure_options": [d.model_dump(mode="json") for d in out["departure_options"]]}

    return app
