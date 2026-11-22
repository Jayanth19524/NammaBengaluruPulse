from __future__ import annotations

import os

from fastapi import FastAPI, HTTPException

from .clients import HttpRoadClient, HttpTripClient
from .config import load_settings
from .graph import Orchestrator
from .models import RunRequest
from .store import Store


def create_app(orch: Orchestrator | None = None) -> FastAPI:
    if orch is None:
        orch = Orchestrator(HttpTripClient(os.environ.get("TRIPCAST_URL", "http://localhost:8003")),
                            HttpRoadClient(os.environ.get("ROADTRUST_URL", "http://localhost:8002")),
                            Store(os.environ.get("ORCHESTRATOR_DB", "orchestrator.db")), load_settings())
    app = FastAPI(title="Orchestrator")

    @app.get("/health")
    def health():
        return {"agent": "Orchestrator", "framework": "langgraph", "relevance_threshold": orch.s.relevance_threshold}

    @app.post("/run")
    def run(req: RunRequest):
        return orch.run(req)

    @app.get("/runs")
    def runs():
        return orch.store.list_runs()

    @app.get("/runs/{run_id}")
    def get_run(run_id: str):
        r = orch.store.get_run(run_id)
        if r is None:
            raise HTTPException(404, "unknown run")
        return r

    @app.get("/alerts")
    def alerts():
        return orch.store.alert_history()

    return app
