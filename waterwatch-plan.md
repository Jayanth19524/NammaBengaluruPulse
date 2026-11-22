# WaterWatch — Full-Stack Plan

## Top-Level Overview

**Goal:** Build a fully working, browser-testable WaterWatch application that lets a user click any location on a 3D map, scan underground water conditions and supply disruptions for that area, and receive actionable alerts and notifications.

**Scope:**
- Monorepo scaffolding (shared contracts, config, design tokens)
- Python WaterWatch agent with mock + real adapters
- Node/Express REST API (backend)
- React + Vite + Tailwind frontend with a 3D/interactive map (Leaflet + react-leaflet + OpenTopoMap terrain tiles — no API key required)
- PostgreSQL + PostGIS database with WaterWatch tables
- In-browser alert/notification panel
- End-to-end runnable with `npm run dev` (web + api) + `uvicorn` (agent) — no Docker required

**Non-goals (MVP):**
- Real BWSSB/live IoT integration (mock adapter covers this; clearly labelled)
- FCM push notifications to mobile (browser toast/alert panel is sufficient for demo)
- FloodLens and RoadTrust agents (out of scope for this slice)

**Key constraints from master prompt:**
- No hardcoded coordinates — use city config
- Mock data always labelled `is_simulated: true`
- No LLM dependency — `recommended_action` text generated from static templates only
- UI: no gradients, no emoji, no "AI-powered" labels; teal accent for water category
- One Node API, one Python agent service, Postgres, Redis

---

## Sub-Task 1 — Monorepo Scaffold + Shared Contracts

**Intent:** Create the folder structure, shared TypeScript/Python contracts, city config, and environment wiring that all subsequent sub-tasks depend on. Without this, nothing else can be built consistently.

**Expected Outcomes:**
- Repo has `apps/api/`, `apps/web/`, `agents/waterwatch/`, `packages/contracts/` directories
- `packages/contracts/src/agentContract.ts` exports the Zod-validated agent response shape
- `agents/waterwatch/contracts/agent_contract.py` exports the matching Pydantic model
- `config/city.json` holds Bengaluru bounding box, default corridor width, severity thresholds — no hardcoded values anywhere else
- `.env.example` documents every required environment variable
- No Docker required; local Postgres + Redis assumed (or SQLite-fallback noted in README)

**Todo List:**
- [ ] Create top-level directories: `apps/api/src/`, `apps/web/src/`, `agents/waterwatch/`, `packages/contracts/src/`, `config/`
- [ ] Write `config/city.json` with Bengaluru bbox, default radius (500 m), severity thresholds
- [ ] Write `packages/contracts/src/agentContract.ts` — Zod schema matching Section 7 of master prompt
- [ ] Write `packages/contracts/src/index.ts` re-exporting all shared types
- [ ] Write `agents/waterwatch/contracts/agent_contract.py` — Pydantic model matching the same shape
- [ ] Write `.env.example` listing `DATABASE_URL`, `REDIS_URL`, `USE_MOCK_ADAPTER`, `PORT`, `PYTHON_AGENT_URL` — no `OPENAI_API_KEY` needed
- [ ] Write `package.json` scripts at root: `dev:api`, `dev:web`, `dev:agent` for running each service locally
- [ ] Write root `README.md` with setup instructions, env vars, and how to run the demo

**Relevant Context:**
- Master prompt Section 7 (agent contract shape)
- Master prompt Section 6 (stack: Node, Python, Postgres+PostGIS, Redis)
- Master prompt working rule: no hardcoded coordinates or thresholds

**Status:** [ ] pending

---

## Sub-Task 2 — Database Schema (WaterWatch Tables)

**Intent:** Create the PostgreSQL + PostGIS schema for all WaterWatch-specific tables plus the shared base tables needed for the app to function. This is the data foundation — every API route and agent result writes to or reads from these tables.

**Expected Outcomes:**
- Migration file(s) in `apps/api/src/db/migrations/` create all required tables
- Tables: `users`, `locations`, `water_incidents`, `sensor_readings`, `agent_investigations`, `notifications`
- Every incident table has: PostGIS `GEOGRAPHY(Point)` column, `severity`, `verification_status`, `is_simulated`, `source`, `observed_at`, `expires_at`, GiST spatial index
- `sensor_readings` has: `device_id`, `location`, `value`, `unit`, `timestamp`, `is_simulated`
- Seed file with clearly labelled demo/simulated data for Bengaluru area

**Todo List:**
- [ ] Set up `apps/api/src/db/` with a migration runner (using `node-postgres` + raw SQL or `drizzle-orm`)
- [ ] Write migration `001_base_tables.sql`: `users`, `locations`
- [ ] Write migration `002_water_incidents.sql`: `water_incidents` with PostGIS geometry, all required columns
- [ ] Write migration `003_sensor_readings.sql`: `sensor_readings` with PostGIS geometry
- [ ] Write migration `004_agent_investigations.sql`: audit log table
- [ ] Write migration `005_notifications.sql`: notifications table
- [ ] Write seed file `seeds/waterwatch_demo.sql` with 5–8 simulated incidents across Bengaluru (`is_simulated = true`)
- [ ] Add GiST indexes on all geometry columns
- [ ] Verify migrations run cleanly via `psql $DATABASE_URL < migration.sql` or migration runner on API startup

**Relevant Context:**
- Master prompt Section 6 (DB table list: WaterIncidents, SensorReadings, etc.)
- PostGIS `ST_DWithin` will be used in API queries for spatial radius search
- `is_simulated` flag is mandatory on every row of simulated data

**Status:** [ ] pending

---

## Sub-Task 3 — WaterWatch Python Agent + Adapters

**Intent:** Build the Python agent (`agents/waterwatch/`) that receives a location (lat/lng + radius), runs the water-scan analysis through adapters, scores severity deterministically, and returns a validated agent contract response. This is the intelligence core.

**Expected Outcomes:**
- `agents/waterwatch/main.py` exposes a FastAPI endpoint `POST /agent/waterwatch/scan`
- Accepts `{ latitude, longitude, radius_m }` and returns one or more agent contract objects
- `MockAdapter` always available, clearly flags `is_simulated: true`, returns realistic demo data
- `BWSSBAdapter` stub (calls a public URL or returns a graceful degradation response)
- `SensorAdapter` stub (accepts ESP32-style telemetry; returns simulated reading with label)
- Scoring engine: deterministic function — inputs are disruption duration, area coverage, report count, sensor deviation; output is `severity` enum. No LLM involvement in scoring.
- `recommended_action` text generated from static templates only — no LLM, no OpenAI dependency
- Pydantic validation on output; malformed output is logged and rejected
- `USE_MOCK_ADAPTER=true` env var switches to mock without code changes

**Todo List:**
- [ ] Scaffold `agents/waterwatch/` with `requirements.txt` (FastAPI, pydantic, httpx, python-dotenv — no openai)
- [ ] Write `agents/waterwatch/contracts/agent_contract.py` — Pydantic model (from Sub-Task 1)
- [ ] Write `agents/waterwatch/adapters/base.py` — `WaterAdapter` abstract base class with `async def fetch(lat, lng, radius) -> list[RawWaterData]`
- [ ] Write `agents/waterwatch/adapters/mock_adapter.py` — returns 3–5 realistic simulated incidents, all `is_simulated=True`
- [ ] Write `agents/waterwatch/adapters/bwssb_adapter.py` — HTTP call to BWSSB/BBMP public feed; graceful degradation on failure
- [ ] Write `agents/waterwatch/adapters/sensor_adapter.py` — accepts telemetry payload; labels simulated data
- [ ] Write `agents/waterwatch/scoring.py` — `compute_severity(duration_hrs, report_count, area_km2, sensor_deviation) -> Severity` — pure function, no randomness, no LLM
- [ ] Write `agents/waterwatch/alert_templates.py` — static template functions, one per `incident_type`; returns specific `recommended_action` string
- [ ] Write `agents/waterwatch/agent.py` — orchestrates: select adapter → fetch → score → pick template for action text → build and validate contract response
- [ ] Write `agents/waterwatch/main.py` — FastAPI app with `POST /agent/waterwatch/scan` and `GET /health`
- [ ] Write basic unit tests in `agents/waterwatch/tests/`: scoring logic, mock adapter output shape, Pydantic validation

**Relevant Context:**
- Master prompt Section 1 (WaterWatch responsibilities: disruption, tanker, IoT, anomaly detection)
- Master prompt Section 7 (agent contract — every field required)
- Master prompt rule: "LLM never invents scores"; mock data always flagged
- No LLM dependency in this implementation — static templates replace LLM for `recommended_action`
- `USE_MOCK_ADAPTER` env var pattern from master prompt working rules

**Status:** [ ] pending

---

## Sub-Task 4 — Node/Express Backend API

**Intent:** Build the REST API layer (`apps/api/`) that the frontend calls. It proxies scan requests to the Python agent, stores results in Postgres, and serves incidents, notifications, and sensor readings back to the UI. This is the bridge between agent intelligence and the browser.

**Expected Outcomes:**
- Express app running on `PORT` (default 4000)
- `POST /api/water/scan` — accepts `{ lat, lng, radius }`, calls Python agent, stores result in `water_incidents`, returns incidents
- `GET /api/water/incidents?lat=&lng=&radius=` — spatial query via PostGIS `ST_DWithin`, returns incidents sorted by severity
- `GET /api/water/sensor/:deviceId` — returns last N readings for a sensor
- `POST /api/water/report` — submit a community shortage report (stored as `verification_status: "reported"`)
- `GET /api/notifications?userId=` — return pending notifications for a user
- All responses include `is_simulated` flag; Zod validates agent contract before DB insert
- SSE endpoint `GET /api/water/stream` for live incident updates
- Rate limiting on all public endpoints

**Todo List:**
- [ ] Scaffold `apps/api/` with `package.json`, TypeScript config, `src/index.ts` (Express entry)
- [ ] Wire `pg` (node-postgres) pool connected to `DATABASE_URL`; run migrations on startup
- [ ] Write `src/routes/water/scan.ts` — calls Python agent via `httpx`-style fetch, validates response with Zod, upserts to `water_incidents`
- [ ] Write `src/routes/water/incidents.ts` — `GET` with PostGIS spatial query
- [ ] Write `src/routes/water/report.ts` — `POST` community report
- [ ] Write `src/routes/water/sensor.ts` — `GET` sensor readings
- [ ] Write `src/routes/water/stream.ts` — SSE, polls Redis pub/sub for new incidents
- [ ] Write `src/routes/notifications.ts` — `GET` notifications
- [ ] Write `src/core/agentProxy.ts` — HTTP client to Python agent with timeout + retry
- [ ] Write `src/core/validate.ts` — Zod validation wrapper (reuses `packages/contracts`)
- [ ] Add `express-rate-limit` middleware
- [ ] Write `src/core/logger.ts` — never logs precise coordinates in plain text
- [ ] Write basic integration test: `POST /api/water/scan` with mock adapter returns valid shape

**Relevant Context:**
- Master prompt Section 6 (Node + Express + TypeScript + REST)
- Master prompt Section 8 (never log precise coordinates; rate-limit; validate all APIs)
- `packages/contracts/src/agentContract.ts` Zod schema used for validation here
- Python agent runs on `PYTHON_AGENT_URL` env var

**Status:** [ ] pending

---

## Sub-Task 5 — Frontend: 3D Map + Click-to-Scan UI

**Intent:** Build the React + Vite frontend with a 3D interactive map where the user clicks a location, triggers a water scan, and sees results as teal markers with a detail panel. This is the primary user-facing experience.

**Expected Outcomes:**
- Vite + React + TypeScript + Tailwind app in `apps/web/`
- 3D/terrain map using **react-leaflet + OpenTopoMap tiles** (free, no API key) centered on Bengaluru
- User clicks any point on the map → scan radius circle drawn → `POST /api/water/scan` called → incidents appear as teal markers
- Clicking a marker opens a detail side panel: incident type, severity badge, basis badge, evidence, recommended action, source, `is_simulated` label if applicable
- Alert/notification panel (top-right or bottom sheet) lists active alerts for the scanned area
- Monitoring status line: "Monitoring · last check 3 min ago" (text + static dot)
- Design follows Section 5 rules: teal accent, Lucide icons, Inter font, no gradients, no emoji
- Fully responsive: works at 360px and 1440px
- Loading skeletons while scan is in progress; error state if API fails; empty state: "No water disruptions found in this area."

**Todo List:**
- [ ] Scaffold `apps/web/` with `npm create vite`, TypeScript template, install Tailwind + PostCSS
- [ ] Configure Tailwind theme tokens: `--color-water: teal`, severity colours (grey/green/yellow/orange/red), typography scale (12/14/16/20/28), 4px grid spacing, radii (6–8px controls, 10–12px panels)
- [ ] Install `react-leaflet`, `leaflet`, and configure **OpenTopoMap** tile layer (`https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png`) for terrain/3D feel — no API key needed
- [ ] Write `src/components/map/WaterMap.tsx` — initialises map centered on Bengaluru, handles click event → extracts lat/lng → calls `useScanWater` hook
- [ ] Write `src/hooks/useScanWater.ts` — React Query mutation: `POST /api/water/scan`, returns incidents list
- [ ] Write `src/components/map/ScanCircle.tsx` — draws a configurable-radius circle around clicked point
- [ ] Write `src/components/map/WaterMarker.tsx` — teal droplet marker; clusters at low zoom; distinct shape from flood/road markers
- [ ] Write `src/components/panels/IncidentDetailPanel.tsx` — side panel (desktop) / bottom sheet (mobile) with all incident fields
- [ ] Write shared badge components: `SeverityBadge.tsx`, `BasisBadge.tsx` (Confirmed solid / Reported outlined / Predicted dashed / Demo plain tag)
- [ ] Write `src/components/panels/AlertPanel.tsx` — lists active alerts for scanned area; each row is `AlertRow.tsx`
- [ ] Write `src/components/StatusLine.tsx` — "Monitoring · last check X min ago", static dot, no animation
- [ ] Write loading skeleton components for map panel and alert list
- [ ] Write empty state: single text line "No water disruptions found in this area."
- [ ] Wire SSE (`GET /api/water/stream`) to auto-update markers without page refresh
- [ ] Test at 360, 768, 1024, 1440 — no horizontal scroll

**Relevant Context:**
- Master prompt Section 5.2: flat surfaces, teal for water, Inter font, Lucide icons, 4px grid
- Master prompt Section 5.1: hard bans — no gradients, no emoji, no "AI-powered" labels
- Master prompt Section 5.3: `BasisBadge` — Confirmed solid, Reported outlined, Predicted dashed, Demo plain
- Master prompt Section 5.4: "Monitoring · last check 3 min ago" is the only status reminder

**Status:** [ ] pending

---

## Sub-Task 6 — Notifications + Alert Copy

**Intent:** Build the notification system that generates plain-language, specific alert copy for water incidents and delivers it to the in-browser alert panel (and optionally browser push). Alert copy is the user-facing output — it must be specific, not generic.

**Expected Outcomes:**
- `apps/api/src/core/notifications.ts` generates alert copy from incident fields using static templates only — no LLM
- Alert copy is specific: "BWSSB reports a 24-hr supply cut near Koramangala 5th Block starting 6 AM tomorrow. Store water tonight." — not "Water risk elevated."
- Every alert has: category, location name (reverse geocoded from OSM), distance, severity, verification status, recommended action, source, timestamp
- Each alert clearly states its basis: **Confirmed observation** / **Community report** / **Prediction** / **Demo data**
- Notifications stored in `notifications` table; deduplication by incident_id
- In-browser alert panel polls `GET /api/notifications` every 30 s (React Query refetch interval)
- Browser Notification API used for foreground alerts (with user consent)

**Todo List:**
- [ ] Write `apps/api/src/core/alertCopy.ts` — static template function: takes `WaterIncident` → returns specific alert string; one template per `incident_type`; no LLM
- [ ] Write `apps/api/src/core/reverseGeocode.ts` — calls Nominatim (OSM) to get neighbourhood name from lat/lng; caches in Redis
- [ ] Write `apps/api/src/core/notifications.ts` — dedup check (incident_id already notified?), insert to `notifications` table, publish to Redis pub/sub
- [ ] Update `src/routes/water/scan.ts` to call `notifications.ts` after inserting incident
- [ ] Write `apps/web/src/hooks/useNotifications.ts` — React Query, polls `GET /api/notifications`, 30 s interval
- [ ] Write `apps/web/src/components/panels/NotificationToast.tsx` — small top-right toast on new alert; plain text, teal left border, no animation
- [ ] Write `apps/web/src/core/browserPush.ts` — requests Notification permission, shows `Notification` on new alert
- [ ] Write alert copy examples in `apps/api/src/core/alertTemplates.ts` for each `incident_type`: `supply_disruption`, `tanker_shortage`, `sensor_anomaly`, `demand_spike`

**Relevant Context:**
- Master prompt Section 4 (alert must include: category, location, distance, severity, verification status, evidence, timestamp, recommended action, source)
- Master prompt Section 4 alert copy rule: plain and specific, not "Risk vector elevated"
- Nominatim reverse geocode: `https://nominatim.openstreetmap.org/reverse?lat=&lon=&format=json`
- Redis pub/sub used to push to SSE stream (from Sub-Task 4)

**Status:** [ ] pending

---

## Sub-Task 7 — End-to-End Wiring, Demo Script + README

**Intent:** Ensure the full application runs in a browser from a single command, all parts connect correctly, demo data loads automatically, and the README documents exactly how to run and test it. This is the "done means works end-to-end" gate.

**Expected Outcomes:**
- `npm run dev` (web + api) + `uvicorn agents/waterwatch/main:app` starts all services — no Docker
- Browser opens at `http://localhost:5173`; map loads centred on Bengaluru
- User clicks a location → scan runs → teal markers appear → detail panel opens → alert panel shows notification
- All demo/simulated data clearly labelled "Demo data" in UI
- `README.md` has: prerequisites (Node 20, Python 3.11, Postgres with PostGIS), `cp .env.example .env`, `npm install`, `uvicorn` command, browser URL, demo walkthrough steps
- `DEMO_SCRIPT.md` documents the exact click sequence to show the app working end-to-end

**Todo List:**
- [ ] Verify all services start locally: `npm run dev:api`, `npm run dev:web`, `uvicorn agents.waterwatch.main:app --reload`
- [ ] Run DB migrations and seed on first start (migration runner called in API `src/index.ts`)
- [ ] Verify `POST /api/water/scan` → Python agent → DB → SSE → frontend marker flow works end-to-end
- [ ] Verify clicking a marker shows the correct detail panel with all required fields
- [ ] Verify alert copy appears in alert panel and is specific (not generic)
- [ ] Verify "Demo data" tag appears on all simulated incidents
- [ ] Write `DEMO_SCRIPT.md`: step-by-step browser demo (open app → click Jayanagar → see supply disruption → open detail → read alert copy)
- [ ] Update `README.md` with final setup instructions and env var table
- [ ] Run agent unit tests (`pytest agents/waterwatch/tests/`)
- [ ] Run API integration test (`npm test` in `apps/api/`)

**Relevant Context:**
- Master prompt Section 9 (MVP demo flow: register home → monitor → scan → alert → map view)
- Master prompt Section 10 (done means: works end to end, tests pass, README present)
- Seed data in `seeds/waterwatch_demo.sql` (from Sub-Task 2) must be loaded before demo

**Status:** [ ] pending

---

## Dependency Order

Sub-Task 1 (scaffold + contracts) must be done first.
Sub-Task 2 (DB schema) depends on Sub-Task 1.
Sub-Tasks 3 and 4 can run in parallel after Sub-Task 2.
Sub-Task 5 (frontend) depends on Sub-Task 4 (API routes exist).
Sub-Task 6 (notifications) depends on Sub-Tasks 4 and 5.
Sub-Task 7 (wiring + demo) depends on all previous sub-tasks.
