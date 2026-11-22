"""
WaterWatch FastAPI service entry point.
Run with: uvicorn main:app --reload --port 8000
"""
import os
import logging
from typing import List

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

from contracts.agent_contract import AgentContract
from agent import WaterWatchAgent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

USE_MOCK = os.getenv("USE_MOCK_ADAPTER", "true").lower() == "true"
agent = WaterWatchAgent(use_mock=USE_MOCK)

app = FastAPI(
    title="WaterWatch Agent",
    description="NammaPulse WaterWatch — water supply monitoring agent",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:4000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ScanRequest(BaseModel):
    latitude: float
    longitude: float
    radius_m: float = 5000.0


class ScanResponse(BaseModel):
    incidents: List[AgentContract]
    adapter: str
    scan_lat: float
    scan_lng: float
    radius_m: float


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "agent": "WaterWatch",
        "use_mock": USE_MOCK,
    }


@app.post("/agent/waterwatch/scan", response_model=ScanResponse)
async def scan(req: ScanRequest):
    if not (-90 <= req.latitude <= 90):
        raise HTTPException(status_code=422, detail="latitude out of range")
    if not (-180 <= req.longitude <= 180):
        raise HTTPException(status_code=422, detail="longitude out of range")
    if req.radius_m <= 0 or req.radius_m > 50000:
        raise HTTPException(status_code=422, detail="radius_m must be 1–50000")

    logger.info(
        "[scan] lat=%.4f lng=%.4f radius=%.0fm mock=%s",
        req.latitude, req.longitude, req.radius_m, USE_MOCK,
    )

    incidents = await agent.scan(req.latitude, req.longitude, req.radius_m)

    return ScanResponse(
        incidents=incidents,
        adapter="mock_adapter" if USE_MOCK else "real",
        scan_lat=req.latitude,
        scan_lng=req.longitude,
        radius_m=req.radius_m,
    )
