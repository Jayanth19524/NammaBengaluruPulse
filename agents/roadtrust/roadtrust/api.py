"""RoadTrust HTTP service (FastAPI). The Node API / orchestrator calls this."""
from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from .adapters.mock import MockRoadAdapter
from .adapters.overpass import OverpassAdapter
from .agent import RoadTrustAgent
from .agent_log import log as agent_log
from .config import load_city
from .detector import load_detector
from .gps import GpsError
from .models import Kind, RepairStatus, Route, Severity
from .store import InMemoryStore


class InvestigateRequest(BaseModel):
    routes: list[Route]


class RepairRequest(BaseModel):
    status: RepairStatus
    source: str
    official: bool = False


def _public(inc) -> dict:
    return inc.model_dump(exclude={"reporter_ids"}, mode="json")


def create_app(agent: RoadTrustAgent | None = None) -> FastAPI:
    if agent is None:
        city = load_city()
        adapters = [OverpassAdapter()]
        if os.environ.get("ROADTRUST_USE_MOCK", "0") == "1":
            adapters.append(MockRoadAdapter())  # labelled is_simulated everywhere
        agent = RoadTrustAgent(
            city, InMemoryStore(city.roadtrust.dedup_radius_m, city.roadtrust.stale_after_days),
            load_detector(), adapters)
    app = FastAPI(title="RoadTrust")

    @app.get("/health")
    def health():
        return {"agent": "RoadTrust", "city": agent.city.id, "detector": agent.detector.name,
                "detector_available": agent.detector.available,
                "adapters": [{"name": a.name, "simulated": a.is_simulated} for a in agent.adapters]}

    @app.post("/reports", status_code=201)
    async def report(lat: float | None = Form(None), lon: float | None = Form(None),
                     kind: Kind = Form("pothole"), severity: Severity = Form("low"),
                     description: str = Form(""), reporter_id: str = Form(...),
                     image: UploadFile | None = File(None)):
        data = await image.read() if image else None
        try:
            inc, created, analysis = agent.submit_report(
                reporter=reporter_id, kind=kind, description=description, latitude=lat,
                longitude=lon, user_severity=severity, image=data)
        except GpsError as exc:
            raise HTTPException(422, str(exc))
        except ValueError as exc:
            raise HTTPException(413, str(exc))
        return {"incident": _public(inc), "created": created, "analysis": analysis}

    @app.post("/investigate")
    def investigate(req: InvestigateRequest):
        try:
            out = agent.investigate(req.routes)
        except ValueError as exc:
            raise HTTPException(422, str(exc))
        return {**out, "responses": [r.model_dump(mode="json") for r in out["responses"]]}

    @app.get("/incidents")
    def incidents():
        return [_public(i) for i in agent.store.active(datetime.now(timezone.utc))]

    @app.post("/incidents/{incident_id}/repair")
    def repair(incident_id: str, req: RepairRequest):
        if agent.store.get(incident_id) is None:
            raise HTTPException(404, "unknown incident")
        inc = agent.store.update_repair(incident_id, req.status, req.source, req.official,
                                        datetime.now(timezone.utc))
        return _public(inc)

    @app.get("/images/{key}")
    def get_image(key: str):
        """Serve a stored (EXIF-stripped) image by its content-addressed key."""
        image_dir = os.environ.get("ROADTRUST_IMAGE_DIR")
        if not image_dir:
            raise HTTPException(404, "image storage not configured")
        # Sanitize key: only hex chars allowed
        if not all(c in "0123456789abcdef" for c in key):
            raise HTTPException(400, "invalid key")
        path = Path(image_dir) / f"{key}.jpg"
        if not path.exists():
            raise HTTPException(404, "not found")
        return FileResponse(str(path), media_type="image/jpeg")

    @app.get("/log")
    def log_stream():
        """Server-sent events stream of real-time agent execution events.
        The UI subscribes to this to show the agent working in real time.
        Each event is a JSON object: {kind, message, data, at}.
        """
        def generate():
            yield from agent_log.sse_stream()

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",   # nginx: disable proxy buffering
                "Connection": "keep-alive",
            },
        )

    @app.get("/log/snapshot")
    def log_snapshot():
        """Return current buffered log events as JSON (for initial page load)."""
        return {"events": agent_log.snapshot()}

    return app
