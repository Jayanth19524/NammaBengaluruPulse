# Orchestrator

LangGraph coordinator for the agents. Owner: shared.

```
plan_regions -> trip (TripCast) -> road (RoadTrust) -> normalize -> dedupe -> score -> decide -> record
                                         \__ no agent data: skip straight to record
```

- **trip**: asks TripCast for the predicted time and alternatives; its route geometry is what RoadTrust is queried with.
- **normalize**: turns agent output into one `Finding` shape. A traffic finding is created only when the predicted time is notably worse than a departure-time estimate, or heavy overall.
- **dedupe**: merges the same incident seen on several routes, and same-kind findings within 25 m.
- **score**: relevance 0-1 from fixed weights (severity, closeness to route, source reliability, confidence). No language model is involved.
- **decide**: alert or suppress with a stated reason: simulated data, category off, below your minimum severity, below the relevance threshold, already alerted within the cooldown (unless it escalated), or over the per-run cap.
- **record**: SQLite stores the run, every step of the decision log, every decision, and alert history.

All thresholds and weights live in `packages/city-config/bengaluru.json` under `orchestrator`. They are starting
values, not tuned against real data.

Degradation: if TripCast or RoadTrust is down, the run continues with what is available, says so in the log and
headline, and is still recorded.

Not yet: sending push notifications (alerts are only recorded), an LLM step for wording, scheduled background runs, FloodLens and WaterWatch.

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest
ORCHESTRATOR_DB=orchestrator.db .venv/bin/uvicorn orchestrator.api:create_app --factory --port 8004
```

`POST /run` with `{routes:[{id,name,origin:[lat,lon],destination:[lat,lon],categories?,min_severity?}]}`; `GET /runs`, `/runs/{id}`, `/alerts`.
