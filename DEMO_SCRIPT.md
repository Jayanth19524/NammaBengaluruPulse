# WaterWatch — Demo Script

This script walks through the complete browser demo end-to-end.

## Prerequisites

All three services must be running (see README.md). Open `http://localhost:5173`.

---

## Step 1 — App loads

**Expected:** Bengaluru terrain map fills the screen. Top bar shows "WaterWatch · NammaPulse" and "Monitoring · last check just now". Right sidebar is empty ("No water alerts for this area."). A hint at the bottom reads "Click anywhere on the map to scan for water issues".

---

## Step 2 — Click Jayanagar (supply disruption area)

Click the map near: **Jayanagar, Bengaluru** (approximately 12.93°N, 77.58°E — south-west of city centre)

**Expected:**
- "Scanning area..." overlay appears briefly
- A teal circle (5 km radius) draws around your click point
- 2–3 teal droplet markers appear in the scan area
- Right sidebar populates with alerts

---

## Step 3 — Open the supply disruption incident

Click the marker at Jayanagar.

**Expected detail panel shows:**
- Title: "Supply disruption"
- Severity badge: **High** (orange dot)
- Basis badge: **Demo data** (plain grey tag)
- Location: "Jayanagar"
- Recommended action: *"Supply disruption near Jayanagar. Store water now. Contact BWSSB on 1916 for updates..."*
- Evidence: "12 community reports in last 2 hrs", "BWSSB maintenance notice #2024-1182"
- Source: "mock_adapter"
- Confidence: 75%

---

## Step 4 — Check the alert panel

Look at the right sidebar (or bottom toast).

**Expected alert copy (not generic):**
> *"Supply disruption near Jayanagar. Store water now. Contact BWSSB on 1916 for updates. Tanker may be available at your ward office. [Demo data]"*

NOT:
> ~~"Water risk elevated in your zone."~~

---

## Step 5 — Click HSR Layout (critical incident)

Click near: **HSR Layout** (approximately 12.91°N, 77.64°E)

**Expected:**
- New scan circle draws
- A red marker appears (critical severity)
- Detail panel shows "Supply disruption" with **Critical** severity badge
- Alert copy: *"Supply cut near HSR Layout. Store water now. Emergency tanker helpline: 1916. [Demo data]"*

---

## Step 6 — Click an area with no incidents

Click far north of the city (above 13.1°N).

**Expected:** "No water disruptions found in this area." message appears at the bottom.

---

## Step 7 — API health check (optional)

Open in browser or curl:

```
http://localhost:4000/health
http://localhost:8000/health
```

Both return `{"status": "ok"}`.

---

## Step 8 — Direct API test (optional)

```bash
curl -X POST http://localhost:4000/api/water/scan \
  -H "Content-Type: application/json" \
  -d '{"lat": 12.9716, "lng": 77.5946, "radius": 10000}'
```

Returns JSON with `incidents` array and `count`. All incidents have `is_simulated: true`.

---

## What to show

1. **Map is the hero** — terrain tiles, clean, no decorations
2. **Teal markers** — distinct from other categories
3. **Detail panel** — all fields present, specific copy, "Demo data" label
4. **Alert panel** — specific, plain language, NOT "Risk vector elevated"
5. **Empty state** — single line of text, no cartoon
6. **Status line** — "Monitoring · last check X min ago", static dot
