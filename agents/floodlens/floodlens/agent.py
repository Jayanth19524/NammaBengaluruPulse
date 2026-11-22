"""FloodLens engine: builds a terrain grid, applies rainfall (forecast or a labelled what-if scenario) and
user waterlogging reports, and finds the flood-risk areas that touch monitored routes."""
from __future__ import annotations

import hashlib
import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .config import DEFAULT_DIR, Settings
from .geo import bbox_of, dist_to_route_m, grid_points, hav
from .model import compute_relief, score_cell
from .models import Cell, Cluster, RainStats, Report, Route, Scenario
from .sources import ElevationSource, RainSource, SourceError

ACTION = {
    "critical": "Avoid this stretch during the rain window. Take an alternative road or delay the trip.",
    "high": "Expect waterlogging here during the rain. Plan an alternative road.",
    "moderate": "Water may collect here in heavy rain. Allow extra time and avoid low underpasses.",
    "low": "Minor water collection is possible here. Drive carefully.",
}


class GpsError(ValueError):
    pass


def city_bbox() -> tuple[float, float, float, float] | None:
    path = Path(os.environ.get("NAMMAPULSE_CITY_DIR", DEFAULT_DIR)) / f"{os.environ.get('NAMMAPULSE_CITY', 'bengaluru')}.json"
    try:
        return tuple(json.loads(path.read_text())["bbox"])
    except (OSError, KeyError, ValueError):
        return None


class Trace:
    def __init__(self):
        self.events: list[dict] = []

    def __call__(self, kind: str, message: str, data: dict | None = None):
        self.events.append({"kind": kind, "message": message, "data": data or {}, "at": datetime.now(timezone.utc).isoformat()})


class FloodLensAgent:
    def __init__(self, settings: Settings, elevation: ElevationSource, rain: RainSource, bbox=None):
        self.s, self.elevation, self.rain, self.bbox = settings, elevation, rain, bbox
        self.reports: list[Report] = []

    # ---- reports (observed waterlogging, community-reported) -----------------
    def add_report(self, lat: float, lon: float, reporter: str, depth_cm: float | None = None, note: str = "",
                   now: datetime | None = None) -> tuple[Report, bool]:
        now = now or datetime.now(timezone.utc)
        if not (-90 <= lat <= 90 and -180 <= lon <= 180) or (lat == 0 and lon == 0):
            raise GpsError("invalid coordinates")
        if self.bbox and not (self.bbox[0] <= lon <= self.bbox[2] and self.bbox[1] <= lat <= self.bbox[3]):
            raise GpsError("location is outside the covered city")
        who = hashlib.sha256(reporter.encode()).hexdigest()[:16]
        for r in self.active_reports(now):
            if r.reporter_hash == who and hav(r.lat, r.lon, lat, lon) <= 50:
                return r, False
        rep = Report(id=uuid.uuid4().hex[:12], lat=lat, lon=lon, at=now, depth_cm=depth_cm, note=note[:200], reporter_hash=who)
        self.reports.append(rep)
        return rep, True

    def active_reports(self, now: datetime) -> list[Report]:
        ttl = timedelta(hours=self.s.report_ttl_h)
        return [r for r in self.reports if now - r.at <= ttl]

    def analysis(self, routes: list[Route], scenario: Scenario | None, now: datetime, trace: Trace | None = None) -> "Analysis":
        return Analysis(self, routes, scenario, now, trace or Trace())

    # ---- deterministic run -----------------------------------------------------
    def run(self, routes: list[Route], scenario: Scenario | None = None, now: datetime | None = None) -> dict:
        now = now or datetime.now(timezone.utc)
        trace = Trace()
        a = self.analysis(routes, scenario, now, trace)
        a.forecast()
        a.cells()
        clusters = [c for r in routes for c in a.clusters(r)]
        return a.result(clusters, {})


class Analysis:
    """One investigation. Lazy steps so the LLM agent can call them in its own order."""

    def __init__(self, agent: FloodLensAgent, routes: list[Route], scenario: Scenario | None, now: datetime, trace: Trace):
        self.agent, self.s, self.routes, self.scenario, self.now, self.trace = agent, agent.s, routes, scenario, now, trace
        self.by_id = {r.id: r for r in routes}
        self.health: list[dict] = []
        self._rain: list[RainStats] | None = None
        self._cells: list[Cell] | None = None
        self.dlat = self.dlon = 0.0
        self.bbox = bbox_of([r.geometry for r in routes], self.s.pad_m)
        self.assessed: dict[str, list[Cluster]] = {}

    def corridor(self, r: Route) -> float:
        return r.corridor_m or self.s.route_corridor_m

    # forecast ------------------------------------------------------------------
    def forecast(self) -> list[RainStats]:
        if self._rain is not None:
            return self._rain
        min_lon, min_lat, max_lon, max_lat = self.bbox
        cx, cy = (min_lon + max_lon) / 2, (min_lat + max_lat) / 2
        pts = [(cy, cx), (min_lat + (max_lat - min_lat) * .25, min_lon + (max_lon - min_lon) * .25),
               (min_lat + (max_lat - min_lat) * .25, min_lon + (max_lon - min_lon) * .75),
               (min_lat + (max_lat - min_lat) * .75, min_lon + (max_lon - min_lon) * .25),
               (min_lat + (max_lat - min_lat) * .75, min_lon + (max_lon - min_lon) * .75)]
        if self.scenario:
            self._rain = [RainStats(lat=la, lon=lo, peak_mm_h=self.scenario.peak_mm_h, accum_6h_mm=self.scenario.accum_6h_mm,
                                    accum_24h_mm=self.scenario.accum_6h_mm) for la, lo in pts]
            self.trace("scenario", f"Using the what-if scenario '{self.scenario.label}' ({self.scenario.accum_6h_mm:g} mm in 6 h, "
                       f"peak {self.scenario.peak_mm_h:g} mm/h). This is not a forecast.", self.scenario.model_dump())
            return self._rain
        self.trace("fetch", f"Fetching the rainfall forecast from {self.agent.rain.name} for {len(pts)} points.")
        try:
            self._rain = self.agent.rain.forecast(pts)
            self.health.append({"source": self.agent.rain.name, "status": "ok"})
            w = self.summary()
            self.trace("forecast", f"Forecast: worst 6 h total {w['accum_6h_mm']} mm, peak {w['peak_mm_h']} mm/h over the next {w['hours']} h.", w)
        except SourceError as exc:
            self._rain = []
            self.health.append({"source": self.agent.rain.name, "status": "unavailable", "error": str(exc)})
            self.trace("error", f"Rainfall forecast unavailable ({exc}); risk cannot be estimated.")
        return self._rain

    def summary(self) -> dict:
        rain = self.forecast()
        if not rain:
            return {"available": False, "is_scenario": bool(self.scenario)}
        worst = max(rain, key=lambda r: (r.accum_6h_mm, r.peak_mm_h))
        return {"available": True, "is_scenario": bool(self.scenario), "label": self.scenario.label if self.scenario else "Forecast",
                "peak_mm_h": worst.peak_mm_h, "accum_6h_mm": worst.accum_6h_mm, "accum_24h_mm": worst.accum_24h_mm,
                "peak_at": worst.peak_at.isoformat() if worst.peak_at else None,
                "window_start": worst.window_start.isoformat() if worst.window_start else None,
                "window_end": worst.window_end.isoformat() if worst.window_end else None, "hours": worst.hours,
                "source": "what-if scenario" if self.scenario else self.agent.rain.name}

    # terrain + risk ---------------------------------------------------------------
    def cells(self) -> list[Cell]:
        if self._cells is not None:
            return self._cells
        rows, self.dlat, self.dlon = grid_points(self.bbox, self.s.grid_spacing_m)
        total = sum(len(r) for r in rows)
        if total > self.s.max_cells:
            self.trace("error", f"Area too large ({total} cells > {self.s.max_cells}); reduce the monitored area.")
            self._cells = []
            return self._cells
        self.trace("fetch", f"Reading elevation for {total} grid cells ({self.s.grid_spacing_m:g} m spacing) from {self.agent.elevation.name}.")
        try:
            flat = [p for row in rows for p in row]
            elev = self.agent.elevation.elevations(flat)
            self.health.append({"source": self.agent.elevation.name, "status": "ok"})
        except SourceError as exc:
            self.health.append({"source": self.agent.elevation.name, "status": "unavailable", "error": str(exc)})
            self.trace("error", f"Elevation data unavailable ({exc}); terrain risk cannot be estimated.")
            self._cells = []
            return self._cells
        it = iter(elev)
        grid = [[next(it) for _ in row] for row in rows]
        relief = compute_relief(grid, self.s.relief_radius_cells)
        rain = self.forecast()
        reports = self.agent.active_reports(self.now)
        cells = []
        for i, row in enumerate(rows):
            for j, (lat, lon) in enumerate(row):
                c = Cell(id=f"{i}_{j}", lat=lat, lon=lon, elevation_m=grid[i][j], relief_m=relief[i][j])
                if rain:
                    nearest = min(rain, key=lambda r: hav(r.lat, r.lon, lat, lon))
                    near_report = any(hav(r.lat, r.lon, lat, lon) <= self.s.report_radius_m for r in reports)
                    score_cell(c, nearest, self.s, near_report)
                cells.append(c)
        self._cells = cells
        lows = sum(c.relief_m >= self.s.relief_full_m / 2 for c in cells)
        flagged = sum(c.risk >= self.s.alert_min_risk for c in cells)
        self.trace("terrain", f"Terrain: {lows} of {len(cells)} cells sit well below their surroundings; {flagged} have flood risk above {self.s.alert_min_risk:g}.",
                   {"cells": len(cells), "low_lying": lows, "at_risk": flagged, "reports": len(reports)})
        return cells

    def clusters(self, route: Route) -> list[Cluster]:
        if route.id in self.assessed:
            return self.assessed[route.id]
        cells = self.cells()
        reach = self.corridor(route) + self.s.grid_spacing_m * 0.75
        near = [(c, dist_to_route_m(c.lat, c.lon, route.geometry)) for c in cells if c.risk >= self.s.alert_min_risk]
        near = [(c, d) for c, d in near if d <= reach]
        parent = list(range(len(near)))

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x
        for i in range(len(near)):
            for j in range(i + 1, len(near)):
                if hav(near[i][0].lat, near[i][0].lon, near[j][0].lat, near[j][0].lon) <= self.s.grid_spacing_m * 1.6:
                    parent[find(i)] = find(j)
        groups: dict[int, list[tuple[Cell, float]]] = {}
        for i, item in enumerate(near):
            groups.setdefault(find(i), []).append(item)
        out = []
        for g in groups.values():
            top = max(g, key=lambda x: x[0].risk)[0]
            out.append(Cluster(id=f"flood:{route.id}:{top.id}", route_id=route.id, lat=top.lat, lon=top.lon, risk=top.risk,
                               severity=top.severity, distance_m=round(min(d for _, d in g), 1), relief_m=top.relief_m,
                               elevation_m=top.elevation_m, n_cells=len(g), reported=any(c.reported for c, _ in g)))
        out.sort(key=lambda c: (-c.risk, c.distance_m))
        self.assessed[route.id] = out
        self.trace("assess", f"{route.name or route.id}: {len(out)} flood-risk area(s) touch the route.", {"route": route.id, "areas": len(out)})
        return out

    # output -----------------------------------------------------------------------
    def geojson(self) -> dict:
        h_lat, h_lon = self.dlat / 2, self.dlon / 2
        feats = []
        for c in self.cells():
            ring = [[c.lon - h_lon, c.lat - h_lat], [c.lon + h_lon, c.lat - h_lat], [c.lon + h_lon, c.lat + h_lat],
                    [c.lon - h_lon, c.lat + h_lat], [c.lon - h_lon, c.lat - h_lat]]
            feats.append({"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [ring]},
                          "properties": {"id": c.id, "risk": c.risk, "severity": c.severity, "relief_m": c.relief_m,
                                         "elevation_m": c.elevation_m, "reported": c.reported, "depression": c.depression}})
        return {"type": "FeatureCollection", "features": feats}

    def response(self, c: Cluster, note: dict | None) -> dict:
        s = self.summary()
        sim = bool(self.scenario)
        ev = [{"type": "model_estimate", "note": "Model estimate from terrain and rainfall. Not a measurement; not validated against past floods."},
              {"type": "terrain", "elevation_m": c.elevation_m, "relief_m": c.relief_m,
               "source": self.agent.elevation.name, "note": "Positive relief means lower than the surroundings, so water collects."}]
        if s.get("available"):
            ev.append({"type": "rainfall_forecast" if not sim else "scenario", "peak_mm_h": s["peak_mm_h"], "accum_6h_mm": s["accum_6h_mm"],
                       "window_start": s["window_start"], "window_end": s["window_end"], "source": s["source"]})
        if c.reported:
            ev.append({"type": "community_report", "note": "Waterlogging recently reported nearby; not independently verified."})
        if note:
            ev.append({"type": "agent_reasoning", "text": note["reasoning"], "model": note.get("model", "")})
        return {"agent": "FloodLens", "incident_id": c.id, "incident_type": "flood_risk",
                "location": {"latitude": c.lat, "longitude": c.lon}, "severity": c.severity,
                "confidence": self.s.report_confidence if c.reported else self.s.base_confidence,
                "verification_status": "reported" if c.reported else "predicted", "affected_route": True,
                "route_id": c.route_id, "distance_m": c.distance_m, "risk": c.risk, "evidence": ev,
                "source": [s.get("source", "")] + ([self.agent.elevation.name]), "is_simulated": sim,
                "recommended_action": (note or {}).get("recommended_action") or ACTION.get(c.severity, ACTION["low"]),
                "observed_at": self.now.isoformat()}

    def result(self, clusters: list[Cluster], notes: dict[str, dict], agent: dict | None = None) -> dict:
        responses = [self.response(c, notes.get(c.id)) for c in clusters]
        self.trace("done", f"{len(responses)} flood-risk finding(s) for your routes.")
        return {"responses": responses, "risk_map": self.geojson(), "forecast": self.summary(), "source_health": self.health,
                "agent": agent or {"mode": "deterministic"}, "trace": self.trace.events if hasattr(self.trace, "events") else [],
                "audit": {"routes": len(self.routes), "cells": len(self.cells()), "at": self.now.isoformat()}}
