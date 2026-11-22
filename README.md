# WaterWatch — NammaPulse

> Click any location on a 3D terrain map of Bengaluru to scan for underground water supply issues. Get specific, plain-language alerts before you're affected.

**Branch:** `waterwatch/full-stack-solution`

---

## What it does

1. User opens the app in a browser — Bengaluru loads on a terrain map
2. User clicks any point on the map
3. A 5 km radius scan fires against the WaterWatch agent
4. Teal markers appear at incident locations
5. Clicking a marker opens a detail panel: severity, basis, evidence, recommended action
6. An alert panel on the right lists active notifications with specific copy

---

## Prerequisites

| Tool | Version | Install |
|---|---|---|
| Node.js | 20+ | https://nodejs.org |
| Python | 3.11+ | https://python.org |
| PostgreSQL | 14+ with PostGIS | https://postgis.net |
| Redis | 7+ | https://redis.io |

> **No Docker required.** All services run locally.

---

## Quick start

### 1. Clone and copy env

```bash
git clone <repo-url>
cd NammaBengaluruPulse
git checkout waterwatch/full-stack-solution
cp .env.example .env
```

Edit `.env` and set your `DATABASE_URL` and `REDIS_URL`.

### 2. Install Node dependencies

```bash
# Install contracts package
cd packages/contracts && npm install && npm run build && cd ../..

# Install API
cd apps/api && npm install && cd ../..

# Install web
cd apps/web && npm install && cd ../..
```

### 3. Install Python dependencies

```bash
cd agents/waterwatch
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt
cd ../..
```

### 4. Set up the database

```bash
# Create the database (replace 'postgres' with your user)
psql -U postgres -c "CREATE DATABASE waterwatch;"

# Migrations and seed run automatically on API startup
# Or run manually:
psql $DATABASE_URL < apps/api/src/db/migrations/001_base_tables.sql
psql $DATABASE_URL < apps/api/src/db/migrations/002_water_incidents.sql
psql $DATABASE_URL < apps/api/src/db/migrations/003_sensor_readings.sql
psql $DATABASE_URL < apps/api/src/db/migrations/004_agent_investigations.sql
psql $DATABASE_URL < apps/api/src/db/migrations/005_notifications.sql
psql $DATABASE_URL < apps/api/src/db/seeds/waterwatch_demo.sql
```

### 5. Start all services

Open **three terminals**:

**Terminal 1 — Python agent:**
```bash
cd agents/waterwatch
.venv\Scripts\activate   # Windows
source .venv/bin/activate # macOS/Linux
uvicorn main:app --reload --port 8000
```

**Terminal 2 — Node API:**
```bash
cd apps/api
npm run dev
# Runs on http://localhost:4000
```

**Terminal 3 — Web app:**
```bash
cd apps/web
npm run dev
# Runs on http://localhost:5173
```

### 6. Open in browser

```
http://localhost:5173
```

---

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `PORT` | `4000` | Node API port |
| `DATABASE_URL` | — | PostgreSQL connection string |
| `REDIS_URL` | `redis://localhost:6379` | Redis connection string |
| `PYTHON_AGENT_URL` | `http://localhost:8000` | Python agent base URL |
| `USE_MOCK_ADAPTER` | `true` | Use mock data (no external APIs needed) |
| `CORS_ORIGIN` | `http://localhost:5173` | Frontend origin for CORS |
| `NODE_ENV` | `development` | Node environment |

---

## API endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/water/scan` | Scan an area — body: `{ lat, lng, radius }` |
| `GET` | `/api/water/incidents?lat=&lng=&radius=` | Incidents near a point |
| `POST` | `/api/water/report` | Submit community shortage report |
| `GET` | `/api/water/sensor/:deviceId` | Sensor readings for a device |
| `POST` | `/api/water/sensor/telemetry` | Ingest ESP32 telemetry |
| `GET` | `/api/notifications` | Recent alerts |
| `PATCH` | `/api/notifications/:id/read` | Mark notification read |
| `GET` | `/api/water/stream` | SSE live update stream |
| `GET` | `/health` | API health check |

Python agent:

| Method | Path | Description |
|---|---|---|
| `POST` | `/agent/waterwatch/scan` | Run WaterWatch scan |
| `GET` | `/health` | Agent health check |

---

## Running tests

```bash
# Python agent unit tests
cd agents/waterwatch
pytest tests/ -v

# Node API tests
cd apps/api
npm test
```

---

## Mock data

All demo incidents have `is_simulated: true` and are labelled **"Demo data"** in the UI. The 7 pre-seeded incidents cover: Jayanagar, Koramangala, Indiranagar, Whitefield, HSR Layout, Malleshwaram, BTM Layout.

Set `USE_MOCK_ADAPTER=false` in `.env` to attempt real BWSSB/sensor adapters (graceful degradation to mock on failure).

---

## Project structure

```
NammaBengaluruPulse/
├── config/
│   └── city.json              # Bengaluru bbox, thresholds (no hardcoded values)
├── packages/contracts/        # Shared Zod + TypeScript types
├── agents/waterwatch/         # Python FastAPI agent
│   ├── adapters/              # MockAdapter, BWSSBAdapter, SensorAdapter
│   ├── contracts/             # Pydantic AgentContract
│   ├── tests/                 # Unit tests
│   ├── agent.py               # Orchestration
│   ├── scoring.py             # Deterministic severity scoring
│   ├── alert_templates.py     # Static alert copy templates
│   └── main.py                # FastAPI entrypoint
├── apps/api/                  # Node/Express REST API
│   └── src/
│       ├── db/                # Migrations, seeds, pool
│       ├── core/              # Logger, validate, agentProxy, alertCopy, notifications
│       └── routes/            # water/scan, water/incidents, notifications
└── apps/web/                  # React + Vite + Tailwind frontend
    └── src/
        ├── components/map/    # WaterMap (OpenTopoMap terrain)
        ├── components/panels/ # IncidentDetailPanel, AlertPanel, Badges
        ├── hooks/             # useScanWater, useNotifications
        └── types/             # TypeScript interfaces
```
