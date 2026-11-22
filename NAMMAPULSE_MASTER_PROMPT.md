# NAMMAPULSE — MASTER DEVELOPMENT PROMPT (v2, with UI/UX Direction)

You are a principal software architect, senior full-stack engineer, AI agent engineer and product designer.

Your task is to build **NammaPulse**, an Agentic Urban Infrastructure Intelligence Platform, initially targeting Bengaluru, India.

Do not build a conventional civic complaint application. Build a proactive, AI-powered platform that monitors infrastructure problems around users' frequently travelled routes and registered locations, investigates potential disruptions, and notifies users before they are affected.

> **Tagline:** Your City, Watching Out for You.

---

## 0. HOW TO WORK (READ FIRST)

1. **Inspect the repository first.** Understand the current architecture, existing functionality and conventions. If the repository is empty, say so and treat it as a greenfield build.
2. **Produce a technical implementation plan** before writing code: module boundaries, API contracts, database schemas, external API dependencies, and which features require simulated data.
3. **Wait for approval** before making large architectural changes.
4. **Implement incrementally**, in small reviewable vertical slices. Each slice must run, be testable and be demonstrable.
5. Keep a short `DECISIONS.md` recording architectural choices and trade-offs.

**Do not:**

- Generate the entire application in one giant code dump.
- Hardcode Bengaluru-specific coordinates, names or thresholds throughout the codebase. Use a reusable **city configuration** so the platform can expand to other cities.
- Fabricate real-time incidents or present simulated data as real.
- Couple the system to one LLM provider. Put the LLM behind a provider-agnostic interface.
- Create unnecessary microservices. Prefer a modular monolith plus one Python agent service.
- Build autonomous agents that take irreversible actions without user approval.

---

## 1. PRODUCT VISION

NammaPulse is a **personal urban infrastructure monitoring assistant**.

Users register:

- Their home location.
- Their office or workplace.
- Their frequently travelled routes.
- Other important locations they want monitored.

The platform continuously monitors the relevant geographical areas using three specialised AI agents:

1. **FloodLens** — flood and waterlogging intelligence.
2. **RoadTrust** — road damage and road infrastructure intelligence.
3. **WaterWatch** — water supply and shortage intelligence.

When an issue is detected near a user's monitored routes or locations, the system evaluates its **severity, confidence and relevance**, then proactively notifies the user.

**Core philosophy:** Users should not have to open the app and search for problems. NammaPulse watches out for them.

---

## 2. THE THREE SPECIALISED AGENTS

### Agent 1 — FloodLens

**Purpose:** Detect and predict flooding and waterlogging that could affect users' everyday routes.

**Responsibilities**

- Integrate weather forecast APIs.
- Monitor rainfall intensity and accumulated rainfall.
- Collect historical flood and waterlogging incidents.
- Analyse elevation and terrain.
- Identify flood-prone road segments.
- Monitor newly reported waterlogging incidents.
- Calculate location-specific flood-risk scores (deterministically).
- Determine whether an affected road segment intersects monitored routes.
- Generate evidence-backed flood alerts.

**Data sources:** Open-Meteo weather APIs, OpenStreetMap, public elevation datasets, historical incident datasets, user-generated reports.

> **Important:** Never claim rainfall alone predicts flooding. Always distinguish **forecasts**, **observed incidents** and **model-derived risk estimates**.

### Agent 2 — RoadTrust

**Purpose:** Monitor road infrastructure and identify hazards affecting users.

**Responsibilities**

- Accept geotagged road-damage reports and uploaded photographs.
- Detect potholes using computer vision (YOLO or an appropriate model).
- Classify road-damage severity.
- Extract and validate GPS coordinates (EXIF and client-supplied).
- Detect duplicate reports.
- Monitor construction and road closures where reliable data is available.
- Maintain road-incident history and track repair status.
- Determine whether an incident affects a monitored route.

**Data sources:** OpenStreetMap, user-submitted photographs, public road-incident datasets, community reports, public construction/closure information where available.

> **Important:** Do not fabricate repair status. Do not claim an incident is independently verified when it is only user-reported.

### Agent 3 — WaterWatch

**Purpose:** Monitor water availability and disruptions affecting users' registered residential and commercial locations.

**Responsibilities**

- Monitor local water-supply disruption reports.
- Track tanker availability and delivery information.
- Detect reported shortages.
- Monitor apartment-level consumption where sensor integration exists.
- Support IoT sensor telemetry (ESP32-based sensors where available).
- Detect abnormal water consumption.
- Forecast water requirements.
- Generate location-specific water-disruption alerts.

**Data sources:** Public water-supply announcements, community reports, tanker information, simulated IoT data for demonstrations, ESP32 integrations.

> **Important:** Keep city-level supply monitoring separate from apartment-level sensor monitoring. Never imply access to private apartment water systems without an explicit integration.

---

## 3. CENTRAL AGENT ORCHESTRATOR

Build a central orchestration service coordinating the three agents.

**Responsibilities**

1. Receive monitored locations and routes.
2. Determine which regions need monitoring.
3. Dispatch queries to FloodLens, RoadTrust and WaterWatch.
4. Collect agent responses.
5. Normalise incident information.
6. Evaluate geographical relevance and severity.
7. Detect duplicate or overlapping alerts.
8. Prioritise important incidents.
9. Send relevant notifications.
10. Maintain an **auditable record** of agent decisions.

**Rules**

- Use **LangGraph** or an equivalent graph-based orchestration framework.
- The central LLM must **not** invent risk scores. Use deterministic calculations and specialised models for domain analysis; use the LLM only for explanation, summarisation and tool routing.
- Agents expose **structured tools** with well-defined input/output schemas.

---

## 4. PERSONALISED ROUTE MONITORING (CORE FEATURE)

Users must be able to:

- Register home and office locations.
- Add frequently travelled routes.
- Select important places to monitor.
- Choose monitoring preferences.
- Enable or disable individual alert categories.

For MVP, users configure routes and locations manually.

Implement a **route monitoring service** that:

1. Retrieves or calculates route geometry.
2. Converts it into geographic road segments.
3. Creates a configurable **monitoring corridor** around the route.
4. Identifies incidents intersecting that corridor.
5. Evaluates whether incidents are relevant.
6. Sends notifications when meaningful changes occur.

Use **PostGIS** for geospatial queries. Do not send alerts merely because an incident is somewhere in the same city — geographic proximity and actual route impact matter.

Support location monitoring independently of route monitoring. WaterWatch primarily monitors registered residential/property locations, not commute routes.

---

## 5. NOTIFICATION INTELLIGENCE

Deliver relevant alerts without overwhelming users.

**Every alert contains:** incident category, incident location, distance from monitored location/route, severity, confidence or verification status, supporting evidence, timestamp, recommended action, source attribution.

**Implement:** duplicate-alert suppression, severity-based prioritisation, configurable notification preferences (including quiet hours), incident expiry, alert history, and push notifications via **Firebase Cloud Messaging**.

**Example copy**

- **FLOOD ALERT:** Heavy rainfall is forecast near a road segment on your usual commute. Historical incidents indicate possible waterlogging.
- **ROAD ALERT:** A newly reported pothole has been detected along your frequently travelled route.
- **WATER ALERT:** A water supply disruption has been reported in your registered residential area.

**Every alert must clearly distinguish between:**

| Basis | Meaning |
|---|---|
| **Confirmed observation** | Directly measured or officially confirmed |
| **Public / community report** | Reported by users or public sources, not independently verified |
| **Prediction / model estimate** | Forecast or derived risk estimate |

---

## 6. UI / UX DIRECTION (NEW — FOLLOW CLOSELY)

### 6.1 Design principles

1. **Calm, not alarmist.** NammaPulse is a quiet guardian. Reserve strong colour and motion for genuinely severe alerts.
2. **Map-centric.** The map is the hero; everything else supports it.
3. **Glanceable first, detail on demand.** A user should understand "am I affected today?" within 3 seconds of opening the app.
4. **Honesty is visible.** Every incident shows its basis (confirmed / reported / predicted), its source and its confidence. Simulated data is always labelled.
5. **Background-first.** The UI must keep communicating that monitoring is happening even when nothing is wrong.
6. **Mobile-first, desktop-excellent.** Most users will open this from a notification on a phone.

### 6.2 Visual language

- **Style:** modern urban-tech SaaS; clean, premium, generous whitespace, soft shadows, 12–16px radii, subtle 1px borders. No visual clutter, no gratuitous gradients.
- **Theme:** light and dark themes, following system preference, with a manual toggle. Both must meet WCAG AA contrast.
- **Typography:** Inter (or Geist) for UI; a tabular/mono face for numbers, coordinates and timestamps. Type scale 12/14/16/20/24/32. Maintain consistent line-heights and spacing on a 4px grid.
- **Colour tokens (define as CSS variables / Tailwind theme, never hardcode hex in components):**
  - Brand: deep indigo/teal primary with one warm accent.
  - Category colours: **Flood = blue**, **Road = amber/orange**, **Water = cyan/teal** (distinct from flood blue — also differentiate by icon and shape, never colour alone).
  - Severity scale: **Info (neutral) → Low (green) → Moderate (yellow) → High (orange) → Critical (red)**.
  - Verification states: **Confirmed** (solid check badge), **Reported** (outlined badge), **Predicted** (dashed outline + sparkle/forecast icon), **Simulated** (hatched "DEMO" badge).
- **Iconography:** one consistent icon set (Lucide). Category icons: droplets/waves (flood), road/cone (road), faucet/tank (water).
- **Motion:** 150–250ms ease-out transitions; a gentle "pulse" ring on the status indicator while agents are investigating; honour `prefers-reduced-motion`.

### 6.3 Core components (build a small design system first)

- `StatusPulse` — live "Watching" indicator with last-checked timestamp.
- `SeverityBadge`, `VerificationBadge`, `CategoryChip`, `SourceChip`.
- `AlertCard` — category icon, headline, location + distance, severity, verification badge, relative time, recommended action, "View on map" CTA, expandable evidence.
- `IncidentMarker` — shape + colour + icon per category and severity; clustered at low zoom.
- `RouteLayer` — route polyline with a translucent monitoring-corridor buffer; affected segments highlighted.
- `AgentCard` — agent name, state (idle / investigating / degraded), last run, sources consulted, findings count.
- `EmptyState` — reassuring ("All clear on your routes. We checked 4 minutes ago.").
- `Skeleton` loaders everywhere; never a blank screen or bare spinner.

### 6.4 Navigation and layout

- **Mobile:** bottom tab bar — **Home · Map · Alerts · Places · More** (Agents and Settings under More).
- **Desktop:** left sidebar navigation, a main content area and a collapsible right-hand detail panel. The map may go full-bleed with floating panels.
- **Top bar:** city selector (from city config), global `StatusPulse`, notification bell with unread count, theme toggle, profile menu.
- Deep links from push notifications must open straight to the **Map** with the relevant incident focused and its detail sheet open (`/map?incident=<id>`).

### 6.5 Screen specifications

**1. Dashboard ("Today")**
- Hero summary card: *"You're clear for today"* / *"2 things may affect your commute"* with a one-line reason and the `StatusPulse`.
- **Commute strip:** home → office route with per-category status chips (Flood / Road) and expected impact.
- **Home strip:** WaterWatch status for registered residential location.
- Recent alerts (max 5) as `AlertCard`s, plus "Incidents near you" mini-map.
- Footer line: "Monitoring in the background · 3 agents active · last cycle 2 min ago".

**2. Interactive Map**
- Leaflet + OpenStreetMap tiles; clustered incident markers; route polylines with corridor buffers.
- Floating filter bar: category toggles, severity filter, verification-basis filter, time window (now / 24h / 7d), "show only my routes".
- Tapping a marker opens a **bottom sheet (mobile) / side panel (desktop)** with incident detail, evidence (photos, rainfall data, sensor charts), source attribution, confidence, and recommended action.
- Legend and layer control; "locate me" only with explicit permission.
- Predicted flood-risk zones render as translucent hatched polygons, visually distinct from observed incidents.

**3. My Locations**
- Cards for Home, Office, Saved places; routes listed with mini map previews.
- **Add-route flow (stepper):** pick origin → pick destination (search + tap on map) → preview route and corridor width slider → choose categories to monitor → set schedule (e.g. weekdays 8–10am) → confirm.
- Per-location/route toggles for each agent; edit and delete with confirmation.

**4. Alerts**
- Tabs: **Active · History**. Filters by category, severity, basis.
- Grouped by day; swipe to dismiss/snooze on mobile.
- Alert detail page: timeline of how the alert evolved (detected → corroborated → escalated → expired/resolved), evidence, sources, and the agent reasoning summary ("Why am I seeing this?").

**5. Agent Intelligence**
- One card per agent with live state, last run, data sources consulted (with health: OK / degraded / using mock data), recent investigations and findings.
- **Investigation log:** expandable, human-readable audit trail of what each agent checked and decided. Explainable, no raw JSON dumps by default (offer "view raw").
- Clear "Using demo data" banner whenever a mock adapter is active.

**6. Settings**
- Monitoring preferences (corridor width, check frequency), per-category alert toggles and minimum severity.
- Notification preferences: channels, quiet hours, digest vs real-time.
- Location permission controls, privacy settings (data retention, export, delete account), data-source transparency.

### 6.6 States, accessibility and responsiveness

- Design every screen for **loading, empty, error, offline and degraded-provider** states.
- WCAG 2.2 AA: keyboard navigable, visible focus rings, ARIA labels on map controls, minimum 44px touch targets, screen-reader-friendly alert announcements, colour never the only signal.
- Breakpoints: 360 / 768 / 1024 / 1440. Test at 360px width. No horizontal scrolling.
- Performance: route-level code splitting, lazy-load the map, virtualised long lists, marker clustering; target LCP < 2.5s on mid-range mobile.
- PWA: installable, offline shell, service worker handling FCM web push.
- Microcopy: plain, specific, human ("Heavy rain is forecast near Silk Board junction between 5–8pm"), never jargon like "risk vector".

### 6.7 UI deliverables for the first slice

Before building screens, deliver: (a) the design tokens file, (b) the component library with a Storybook-style preview page, (c) the app shell with navigation, (d) the Dashboard and Map screens wired to mock data. Share these for review before building the remaining screens.

---

## 7. TECHNOLOGY STACK

Use the following unless the existing repository has a compelling reason to retain a different stack.

**Frontend:** React, TypeScript, Vite, Tailwind CSS, React Query, React Router, Leaflet with OpenStreetMap.

**Backend:** Node.js, Express, TypeScript, REST APIs, WebSockets (or SSE) for live agent/alert updates.

**AI and agents:** Python, LangGraph, OpenAI API (behind a provider-agnostic interface), YOLO for road-damage detection.

**Data:** PostgreSQL + PostGIS, Redis for caching and job coordination.

**Background processing:** BullMQ or AWS SQS; scheduled monitoring jobs.

**Notifications:** Firebase Cloud Messaging.

**Storage:** S3-compatible object storage for incident images.

---

## 8. DATABASE DESIGN

Design normalised schemas for: Users, Organizations, Locations, MonitoredRoutes, RouteSegments, InfrastructureIncidents, FloodIncidents, RoadIncidents, WaterIncidents, AgentInvestigations, AgentResults, Notifications, NotificationPreferences, SensorReadings, DataSources, IncidentEvidence.

- Use PostGIS geometry/geography types for geographical entities.
- Add GiST spatial indexes plus appropriate B-tree indexes.
- Maintain timestamps, provenance and verification status on every incident record.

---

## 9. AGENT COMMUNICATION CONTRACT

Every agent returns a consistent, validated structured response. Schema example (not hardcoded data):

```json
{
  "agent": "FloodLens",
  "incident_type": "waterlogging",
  "location": { "latitude": 0.0, "longitude": 0.0 },
  "severity": "high",
  "confidence": 0.0,
  "verification_status": "reported",
  "basis": "observation | report | prediction",
  "affected_route": true,
  "evidence": [],
  "source": [],
  "recommended_action": "string",
  "observed_at": "ISO-8601 timestamp",
  "is_simulated": false
}
```

Validate all agent responses (Zod on the Node side, Pydantic on the Python side). Reject and log malformed output.

---

## 10. FAILURE HANDLING AND MOCK DATA

- The demo must work even when external providers are unavailable, using **clearly labelled mock data adapters** (`is_simulated: true`, visible "DEMO" badge in the UI).
- Every adapter implements a common interface so mock and real providers are interchangeable via configuration.
- Use timeouts, retries with backoff, circuit breakers and graceful degradation; surface provider health in the Agent Intelligence screen.

---

## 11. SECURITY AND PRIVACY

- Treat home/office locations as sensitive: encrypt at rest where practical, minimise retention, and never log precise coordinates in plain application logs.
- Authenticated APIs, input validation, rate limiting, secrets via environment variables, image upload validation and EXIF stripping before public display.
- Explicit consent for location access and notifications; provide data export and deletion.

---

## 12. MVP ACCEPTANCE CRITERIA

The first working demonstration must support this scenario end to end:

1. A user registers their home and office.
2. The user adds a frequently travelled route.
3. The platform starts monitoring the route.
4. FloodLens retrieves weather and flood-related information.
5. RoadTrust retrieves road-damage incidents.
6. WaterWatch monitors water disruptions near the registered home.
7. The orchestrator aggregates the results.
8. The notification engine decides whether an alert is relevant.
9. The user receives a notification.
10. The user opens the notification and sees the affected location on the map.

---

## 13. DEFINITION OF DONE

- Working end-to-end workflow, not a UI prototype.
- Reliable ingestion, accurate geospatial filtering, modular agents, explainable intelligence, useful notifications.
- Strong error handling, unit/integration tests for scoring, geospatial filtering, dedup and schema validation.
- README with setup, environment variables, architecture diagram and demo script.
- UI matches Section 6 and passes accessibility checks.

**Start now by inspecting the repository, then produce the architecture and implementation plan (including the UI plan from Section 6.7). Wait for approval before large architectural changes.**

---

*NAMMAPULSE — YOUR CITY, WATCHING OUT FOR YOU.*
