# NAMMAPULSE — MASTER DEVELOPMENT PROMPT (v3)

You are a senior full-stack engineer, AI agent engineer and product designer working on **NammaPulse**, an agentic urban infrastructure monitoring platform, starting with Bengaluru, India.

> **Tagline:** Your City, Watching Out for You.

This is **not** a civic complaint app. Users register their home, office and regular routes. Three AI agents watch the areas around them in the background and send an alert **before** the user is affected. Users should not have to go looking for problems.

---

## 0. TEAM SETUP — ONE PERSON, ONE AGENT

Three people, one agent each. Everyone works in their own folder and does not edit another person's folder without asking.

| Owner | Agent | Owns (vertical slice) |
|---|---|---|
| Member A | **FloodLens** | `agents/floodlens/`, flood adapters, flood DB tables, flood API routes, flood map layer + alert copy |
| Member B | **RoadTrust** | `agents/roadtrust/`, YOLO pipeline, road adapters, road DB tables, road API routes, road map layer + alert copy |
| Member C | **WaterWatch** | `agents/waterwatch/`, sensor/tanker adapters, water DB tables, water API routes, water panel + alert copy |

**Shared code** (`packages/contracts`, `apps/web/src/design`, `apps/api/src/core`, orchestrator, notification engine) is built together in **Phase 0** and then changes only through a small PR that the other two approve.

**Phase 0 — build together first (about 1–2 days):**
1. Freeze the **agent contract** (Section 7), the **city config** format, and the shared DB base tables (users, locations, routes, incidents, notifications).
2. Build the **design tokens + app shell** (Section 5) so everyone's UI looks like one product.
3. Ship a **mock agent** that returns a valid response end to end: route → orchestrator → alert → map. Each person then replaces the mock with their real agent.

**Phase 1 — parallel, each person on their own agent:** real data adapters, scoring, tests, UI panel. Every agent must also work with its **mock adapter** so nobody is blocked by another person's work or by a flaky API.

**Phase 2 — integrate:** orchestrator dedup/prioritisation, notification engine, full demo scenario.

**Working rules**
- Inspect the repo first. If it is empty, say so and plan from scratch. Post a short plan and wait for approval before big architectural changes.
- Small PRs, one concern each. Branch per agent: `floodlens/*`, `roadtrust/*`, `waterwatch/*`.
- Do not hardcode Bengaluru coordinates or thresholds in code. Use a city config.
- Do not fabricate real incidents or pass off simulated data as real. Mock data is always flagged.
- Do not tie the project to one LLM provider. Put it behind a small interface.
- No extra microservices. One Node API, one Python agent service, Postgres, Redis.
- Agents never take irreversible actions without user approval.

---

## 1. THE THREE AGENTS

### FloodLens — flooding and waterlogging
- Pull forecasts and rainfall (Open-Meteo), terrain/elevation, OpenStreetMap roads, historical waterlogging incidents and user reports.
- Compute a **deterministic** flood-risk score per road segment. The LLM never invents scores.
- Check whether risky segments intersect a user's route corridor.
- Rainfall alone does not predict flooding. Always label each finding as a **forecast**, an **observed incident** or a **model estimate**.

### RoadTrust — road damage and closures
- Accept geotagged photos and reports. Detect potholes with YOLO (or similar), classify severity, validate GPS, detect duplicates.
- Track incident history and repair status. Include closures/construction only from reliable public data.
- Never invent repair status. A user report is "reported", not "verified".

### WaterWatch — water supply
- Monitor supply disruption reports, tanker info, shortages. Support IoT/ESP32 telemetry, anomaly detection and demand forecasting.
- Watches **registered homes/properties**, not commute routes.
- Keep city-level supply news separate from apartment-level sensors. Never imply access to a private water system without an explicit integration. Simulated sensor data is labelled as simulated.

---

## 2. ORCHESTRATOR

Graph-based (LangGraph or equivalent). It: receives monitored places and routes → decides which regions to check → dispatches to the three agents → collects and validates responses → normalises incidents → checks geographic relevance and severity → removes duplicates → prioritises → hands off to notifications → writes an **audit log** of every decision.

Agents expose tools with clear input/output schemas. The LLM is for explanation and routing only, never for risk numbers.

---

## 3. ROUTE MONITORING

Users add home, office, saved places and regular routes (manual setup for MVP), and can switch each alert category on or off.

The route service gets or calculates route geometry → splits it into road segments → builds a configurable **monitoring corridor** → finds incidents inside it (PostGIS) → judges relevance → alerts on meaningful change. An incident somewhere in the same city is **not** a reason to alert. Location monitoring works independently of route monitoring.

---

## 4. NOTIFICATIONS

Every alert has: category, location, distance from the route/place, severity, verification status, evidence, timestamp, recommended action, source.

Required: duplicate suppression, severity prioritisation, user preferences and quiet hours, incident expiry, alert history, push via Firebase Cloud Messaging.

Each alert must say which of these it is: **Confirmed observation**, **Public/community report**, or **Prediction**.

Copy is plain and specific. Example: *"Heavy rain forecast 5–8 pm near Silk Board junction. This stretch has flooded before. Your 8:30 commute may be affected."* Not: *"Risk vector elevated."*

---

## 5. UI DIRECTION — CLEAN, NO AI SLOP

The UI should feel like a well-made tool from a small, careful product team (think Linear, Mapbox Studio, Apple Maps). Calm, precise, quiet. It is judged by restraint.

### 5.1 Hard bans (these make it look AI-generated)
- No purple/indigo-to-pink gradients, no glassmorphism blobs, no glowing neon, no gradient text.
- No emoji in the UI. No sparkle/magic-wand icons for "AI". Do not label things "AI-powered" or "Smart".
- No hero-style marketing copy inside the app. No "Welcome back, superstar!".
- No identical rounded cards with a big icon in a coloured circle repeated six times.
- No decorative illustrations, stock imagery, or lorem-ipsum-style filler text. Empty states use one line of text, not a cartoon.
- No shadows stacked on shadows, no oversized radii on everything, no drop-shadowed buttons.
- No random animation. No bouncing, shaking, confetti, or looping effects.
- No fake data that looks real: no invented incident counts, names or "live" numbers.

### 5.2 What to do instead
- **Flat, calm surfaces.** One neutral background, white (or near-black in dark mode) panels, 1px hairline borders, at most one subtle shadow level used only for floating map panels.
- **One accent colour** (a restrained blue or teal) for primary actions and focus. Colour is otherwise reserved for **meaning**: category and severity only.
- **Typography does the work.** One sans family (Inter or Geist), a tabular/mono variant for numbers, times and coordinates. Scale 12 / 14 / 16 / 20 / 28. Sentence case everywhere. Clear weight hierarchy (400/500/600); no bold-everything.
- **Spacing:** 4px grid, consistent paddings, aligned edges. Dense where data lives (lists, tables), airy only around the primary summary.
- **Radii:** 6–8px for controls, 10–12px for panels. Same everywhere.
- **Icons:** one set (Lucide), 1.5px stroke, used sparingly and only when they add meaning.
- **Information first.** Prefer a clear row of text with a small status indicator over a big card with an icon.
- **Map is the hero.** Muted, desaturated basemap so incidents stand out. Markers are small, legible, clustered at low zoom.

### 5.3 Meaning through colour (and never colour alone)
- Categories: Flood = blue, Road = amber, Water = teal. Also differ by **icon and marker shape**.
- Severity: Info grey · Low green · Moderate yellow · High orange · Critical red. Shown as a small dot/label with text, not a whole coloured card.
- Basis badges: **Confirmed** solid · **Reported** outlined · **Predicted** dashed outline · **Demo/Simulated** a plain "Demo data" tag.
- Define all colours as CSS variables/Tailwind theme tokens. No raw hex in components. Light and dark themes both pass WCAG AA.

### 5.4 Navigation and screens
- **Mobile:** bottom tabs — Today · Map · Alerts · Places · More. **Desktop:** left sidebar, main area, optional right detail panel.
- A single small status line, "Monitoring · last check 3 min ago", is the only constant reminder that work happens in the background. It is text plus a small static dot, not a pulsing widget.
- Push notifications deep-link to `/map?incident=<id>` with the incident focused.

1. **Today** — one plain sentence ("Nothing affecting your routes" or "2 issues on your commute"), commute row with per-category status, home water status, last five alerts as a list.
2. **Map** — Leaflet + OSM; route lines with a faint corridor; filters for category, severity, basis and time; tap a marker for a bottom sheet (mobile) or side panel (desktop) with evidence, source, confidence, action. Predicted flood zones are hatched polygons, visually distinct from observed incidents.
3. **Places** — Home, Office, saved places and routes. Add-route is a simple step flow: origin → destination → preview and corridor width → categories → schedule → confirm.
4. **Alerts** — Active / History, filterable, with a "Why am I seeing this?" explanation and a short timeline (detected → corroborated → escalated → expired).
5. **Agents** — one plain row per agent: state, last run, sources used and their health. Readable investigation log, "view raw" optional. A visible "Using demo data" notice whenever a mock adapter is active.
6. **Settings** — monitoring and notification preferences, quiet hours, location permission, privacy, export/delete data.

### 5.5 Quality bar
- Every screen has loading (skeletons), empty, error, offline and degraded-provider states.
- Keyboard accessible, visible focus, 44px touch targets, ARIA on map controls, WCAG 2.2 AA.
- Test at 360, 768, 1024, 1440. No horizontal scroll.
- Lazy-load the map, code-split routes, cluster markers.
- Installable PWA with FCM web push.

### 5.6 Ownership of UI
Shared tokens, shell and base components (`SeverityBadge`, `BasisBadge`, `CategoryChip`, `AlertRow`, `IncidentMarker`, `RouteLayer`) are built in Phase 0. After that each person builds **only their own agent's** UI: map layer, incident detail, alert copy, and their row on the Agents screen. Do not fork the shared components; extend them through props.

---

## 6. STACK

- **Frontend:** React, TypeScript, Vite, Tailwind, React Query, React Router, Leaflet + OSM.
- **Backend:** Node, Express, TypeScript, REST, WebSockets/SSE for live updates.
- **Agents:** Python, LangGraph, OpenAI API behind an interface, YOLO.
- **Data:** PostgreSQL + PostGIS, Redis. Jobs: BullMQ or SQS. Push: FCM. Images: S3-compatible storage.
- Keep the existing repo's stack if it has a good reason to differ.

**Database:** normalised tables for Users, Organizations, Locations, MonitoredRoutes, RouteSegments, InfrastructureIncidents, FloodIncidents, RoadIncidents, WaterIncidents, AgentInvestigations, AgentResults, Notifications, NotificationPreferences, SensorReadings, DataSources, IncidentEvidence. PostGIS geometry with GiST indexes. Timestamps, provenance and verification status on every incident.

---

## 7. AGENT CONTRACT (frozen in Phase 0)

Every agent returns this shape, validated with Zod (Node) and Pydantic (Python). Malformed output is rejected and logged. Values below are placeholders, not data.

```json
{
  "agent": "FloodLens | RoadTrust | WaterWatch",
  "incident_type": "string",
  "location": { "latitude": 0.0, "longitude": 0.0 },
  "severity": "info | low | moderate | high | critical",
  "confidence": 0.0,
  "verification_status": "confirmed | reported | predicted",
  "affected_route": true,
  "evidence": [],
  "source": [],
  "recommended_action": "string",
  "observed_at": "ISO-8601",
  "is_simulated": false
}
```

Every external adapter implements the same interface, so mock and real providers swap by config. Use timeouts, retries with backoff and graceful degradation.

---

## 8. SECURITY AND PRIVACY
Home and office locations are sensitive: minimise retention, never log precise coordinates in plain logs, authenticate and validate every API, rate-limit, keep secrets in env vars, strip EXIF from public images, ask explicit consent for location and notifications, support data export and deletion.

---

## 9. MVP DEMO (must work even if every external API is down, using labelled mock adapters)
1. User registers home and office.
2. User adds a regular route.
3. Platform starts monitoring it.
4. FloodLens gets weather and flood info.
5. RoadTrust gets road-damage incidents.
6. WaterWatch checks disruptions near home.
7. Orchestrator aggregates.
8. Notification engine decides what is relevant.
9. User gets a push notification.
10. User taps it and sees the affected spot on the map.

## 10. DONE MEANS
Works end to end, not just screens. Tests for scoring, geospatial filtering, dedup and schema validation. README with setup, env vars and demo script. UI follows Section 5 and has none of the Section 5.1 bans.

**Start by inspecting the repo and posting a short plan covering Phase 0 and each person's slice. Wait for approval before large changes.**

*NAMMAPULSE — YOUR CITY, WATCHING OUT FOR YOU.*
