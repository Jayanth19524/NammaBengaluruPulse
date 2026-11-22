# RoadTrust

Road damage and road infrastructure agent. Owner: Member B.

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest
.venv/bin/uvicorn roadtrust.api:create_app --factory --port 8002
```

| Endpoint | Purpose |
|---|---|
| `POST /reports` | Multipart report: `lat`, `lon` (or EXIF GPS), `kind`, `severity`, `reporter_id`, optional `image` |
| `POST /investigate` | `{routes:[{id, geometry:[[lon,lat]...], corridor_m?}]}` returns contract responses, source health, audit |
| `GET /incidents` | Active incidents (reporter identities never included) |
| `POST /incidents/{id}/repair` | Record a repair claim. Only `official: true` can mark `repaired` |
| `GET /health` | Detector and adapter status |

## Honesty rules enforced in code
- User reports are `reported`, never `confirmed`. Photos and CV detections add evidence and set severity but do not verify.
- No model weights (`ROADTRUST_YOLO_WEIGHTS`) means no analysis: the response says `cv_run: false` and the photo is stored as `analysed: false`. It is never reported as "no damage".
- A user cannot mark a road `repaired`; it becomes `repair_reported`. Only an official source can set `repaired`.
- Mock data (`ROADTRUST_USE_MOCK=1`, default) is `is_simulated: true` and labelled "(demo data)" in sources and health.
- Incidents are returned only if inside the route's corridor (default from `packages/city-config`).

## Not done yet
- YOLO weights: bring a trained pothole model; `ultralytics` is an optional install.
- Postgres/PostGIS store (`db/migrations/002_roadtrust.sql` is a draft, never run); the service uses an in-memory store.
- Auth, rate limiting, object storage and EXIF stripping for stored images.
- Node API routes and the RoadTrust UI slice, which wait on the Phase 0 shell and design tokens.
