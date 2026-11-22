"""LangGraph orchestration.

plan_regions -> trip -> road -> (normalize -> dedupe -> score -> decide | skip) -> record

Every node appends human-readable events to the audit trail. Scores and alert decisions
are deterministic (config thresholds), never produced by a language model.
"""
from __future__ import annotations

import math
import operator
import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated, Callable, TypedDict

from langgraph.graph import END, START, StateGraph

from .clients import AgentUnavailable, RoadClient, TripClient
from .config import Settings
from .models import SEV_ORDER, Decision, Finding, MonitoredRoute, RunRequest
from .store import Store

DEFAULT_CORRIDOR_M = 50.0
NEAR_DUP_M = 25.0
KIND_LABEL = {"pothole": "Pothole", "road_damage": "Road damage", "closure": "Road closure",
              "construction": "Construction", "other": "Road issue"}


class State(TypedDict, total=False):
    request: RunRequest
    run_id: str
    now: datetime
    events: Annotated[list[dict], operator.add]
    trips: dict[str, dict]
    geometries: dict[str, list]
    road: dict
    findings: list[Finding]
    decisions: list[Decision]
    degraded: list[str]
    summary: dict


def _ev(node: str, message: str, level: str = "info", **data) -> list[dict]:
    return [{"node": node, "level": level, "message": message, "data": data}]


def _hav(lat1, lon1, lat2, lon2) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return 2 * 6_371_008.8 * math.asin(math.sqrt(a))


def _min(n: float) -> str:
    return f"{round(n / 60)} min"


class Orchestrator:
    def __init__(self, trip: TripClient, road: RoadClient, store: Store, settings: Settings,
                 clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc)):
        self.trip, self.road, self.store, self.s, self.clock = trip, road, store, settings, clock
        self.graph = self._build()

    # ---- graph wiring ---------------------------------------------------
    def _build(self):
        g = StateGraph(State)
        for name in ("plan_regions", "trip", "road", "normalize", "dedupe", "score", "decide", "record"):
            g.add_node(name, getattr(self, f"n_{name}"))
        g.add_edge(START, "plan_regions")
        g.add_edge("plan_regions", "trip")
        g.add_edge("trip", "road")
        g.add_conditional_edges("road", self.after_road, {"normalize": "normalize", "record": "record"})
        g.add_edge("normalize", "dedupe")
        g.add_edge("dedupe", "score")
        g.add_edge("score", "decide")
        g.add_edge("decide", "record")
        g.add_edge("record", END)
        return g.compile()

    def run(self, request: RunRequest) -> dict:
        out = self.graph.invoke({"request": request, "run_id": uuid.uuid4().hex[:12], "now": self.clock(),
                                 "events": [], "trips": {}, "geometries": {}, "road": {}, "findings": [],
                                 "decisions": [], "degraded": []})
        return self.store.get_run(out["run_id"])

    # ---- nodes ----------------------------------------------------------
    def n_plan_regions(self, st: State):
        routes = st["request"].routes
        ev = _ev("plan_regions", f"Monitoring {len(routes)} route(s)",
                 routes=[{"id": r.id, "categories": r.categories, "min_severity": r.min_severity} for r in routes])
        return {"events": ev}

    def n_trip(self, st: State):
        """TripCast: predicted time and alternatives. Also yields the route geometry RoadTrust needs."""
        trips, geoms, degraded, ev = {}, {}, [], []
        for r in st["request"].routes:
            try:
                plan = self.trip.plan(r.origin, r.destination, st["request"].depart_at)
                primary = min(plan["routes"], key=lambda p: p["prediction"]["free_flow_s"])
                trips[r.id] = {"plan": plan, "primary": primary}
                geoms[r.id] = [tuple(c) for c in primary["geometry"]]
                p = primary["prediction"]
                ev += _ev("trip", f"TripCast: {r.id} expected {_min(p['predicted_s'])} "
                          f"(departure-time estimate {_min(p['snapshot_s'])}, free-flow {_min(p['free_flow_s'])}); "
                          f"{len(plan['routes'])} candidate route(s)", route=r.id, basis=p["basis"])
            except (AgentUnavailable, KeyError, ValueError) as exc:
                degraded.append(f"TripCast ({r.id})")
                ev += _ev("trip", f"TripCast unavailable for {r.id}: {exc}", level="warn", route=r.id)
                if r.geometry:
                    geoms[r.id] = [tuple(c) for c in r.geometry]
                    ev += _ev("trip", f"Using the geometry supplied for {r.id} so road checks can continue", route=r.id)
        return {"trips": trips, "geometries": geoms, "degraded": degraded, "events": ev}

    def n_road(self, st: State):
        wanted = [r for r in st["request"].routes if "road" in r.categories and r.id in st["geometries"]]
        skipped = [r.id for r in st["request"].routes if "road" in r.categories and r.id not in st["geometries"]]
        ev = [e for rid in skipped for e in _ev("road", f"No route geometry for {rid}: road check skipped", level="warn", route=rid)]
        if not wanted:
            return {"events": ev + _ev("road", "No routes to check for road incidents")}
        payload = [{"id": r.id, "geometry": st["geometries"][r.id], "corridor_m": r.corridor_m} for r in wanted]
        try:
            resp = self.road.investigate(payload)
            health = resp.get("source_health", [])
            bad = [h["source"] for h in health if h.get("status") != "ok"]
            ev += _ev("road", f"RoadTrust returned {len(resp['responses'])} incident(s) in your corridors", sources=health,
                      audit=resp.get("audit"))
            for b in bad:
                ev += _ev("road", f"RoadTrust data source degraded: {b}", level="warn")
            return {"road": resp, "events": ev, "degraded": st["degraded"] + [f"RoadTrust source: {b}" for b in bad]}
        except (AgentUnavailable, KeyError) as exc:
            return {"events": ev + _ev("road", f"RoadTrust unavailable: {exc}", level="warn"),
                    "degraded": st["degraded"] + ["RoadTrust"]}

    def after_road(self, st: State) -> str:
        return "normalize" if (st["trips"] or st["road"]) else "record"

    def n_normalize(self, st: State):
        routes = {r.id: r for r in st["request"].routes}
        findings, ev = [], []
        for w in st["road"].get("responses", []):
            r = routes.get(w["route_id"])
            corridor = (r.corridor_m if r and r.corridor_m else DEFAULT_CORRIDOR_M)
            kind = w["incident_type"]
            d = w.get("distance_m")
            findings.append(Finding(
                key=f"road:{w['incident_id']}", agent="RoadTrust", category="road", kind=kind,
                title=f"{KIND_LABEL.get(kind, 'Road issue')} {round(d)} m from {r.name or r.id if r else w['route_id']}" if d is not None
                else KIND_LABEL.get(kind, "Road issue"),
                lat=w["location"]["latitude"], lon=w["location"]["longitude"], severity=w["severity"],
                basis=w["verification_status"], confidence=w["confidence"], route_ids=[w["route_id"]],
                distance_m=d, corridor_m=corridor, evidence=w.get("evidence", []), sources=w.get("source", []),
                action=w["recommended_action"], observed_at=w["observed_at"], simulated=w.get("is_simulated", False),
                incident_id=w["incident_id"]))
        t = self.s.traffic
        for rid, tr in st["trips"].items():
            r = routes[rid]
            if "traffic" not in r.categories:
                continue
            plan, prim = tr["plan"], tr["primary"]
            p = prim["prediction"]
            surprise = p["predicted_s"] - p["snapshot_s"]
            ratio = p["predicted_s"] / p["free_flow_s"] if p["free_flow_s"] else 1.0
            surprising = surprise >= t.min_surprise_s and p["snapshot_s"] > 0 and surprise / p["snapshot_s"] >= t.min_surprise_ratio
            if not (surprising or ratio >= t.severe_ratio):
                ev += _ev("normalize", f"{rid}: no notable traffic change (expected {_min(p['predicted_s'])}, ratio {ratio:.2f})", route=rid)
                continue
            sev = next((s for lim, s in t.severity_by_ratio if ratio >= lim), "info")
            alt = _best_alt(plan, prim, t.min_alt_saving_s)
            action = "Leave a little earlier or expect delays."
            evidence = [{"type": "trip_prediction", "predicted_s": p["predicted_s"], "snapshot_s": p["snapshot_s"],
                         "free_flow_s": p["free_flow_s"], "range_s": [p["low_s"], p["high_s"]], "basis": p["basis"]}]
            if alt:
                action = f"Consider {'via ' + ' / '.join(alt['via']) if alt['via'] else 'the alternative road'}: about {_min(alt['saves_s'])} faster."
                evidence.append({"type": "alternative_route", "via": alt["via"], "saves_s": alt["saves_s"]})
            title = (f"Traffic likely to build on {r.name or rid}: about {_min(p['predicted_s'])}, "
                     f"not the {_min(p['snapshot_s'])} shown at departure" if surprising
                     else f"Heavy traffic expected on {r.name or rid}: about {_min(p['predicted_s'])}")
            findings.append(Finding(
                key=f"traffic:{rid}", agent="TripCast", category="traffic", kind="traffic_delay", title=title,
                severity=sev, basis="predicted", confidence=0.65 if plan.get("live_traffic") else 0.5,
                route_ids=[rid], evidence=evidence, sources=[p["basis"]], action=action, observed_at=st["now"]))
        ev = _ev("normalize", f"Normalised {len(findings)} finding(s)", road=sum(f.category == "road" for f in findings),
                 traffic=sum(f.category == "traffic" for f in findings)) + ev
        return {"findings": findings, "events": ev}

    def n_dedupe(self, st: State):
        out: list[Finding] = []
        ev = []
        for f in st["findings"]:
            match = next((o for o in out if o.key == f.key), None)
            reason = "same incident"
            if match is None and f.lat is not None:
                match = next((o for o in out if o.lat is not None and o.kind == f.kind
                              and _hav(o.lat, o.lon, f.lat, f.lon) <= NEAR_DUP_M), None)
                reason = f"same kind within {NEAR_DUP_M:.0f} m"
            if match is None:
                out.append(f)
                continue
            for rid in f.route_ids:
                if rid not in match.route_ids:
                    match.route_ids.append(rid)
            if f.distance_m is not None and (match.distance_m is None or f.distance_m < match.distance_m):
                match.distance_m = f.distance_m
            if SEV_ORDER.index(f.severity) > SEV_ORDER.index(match.severity):
                match.severity = f.severity
            match.sources = list(dict.fromkeys(match.sources + f.sources))
            ev += _ev("dedupe", f"Merged duplicate: {f.title} into {match.title} ({reason})", keys=[match.key, f.key])
        ev = _ev("dedupe", f"{len(st['findings'])} finding(s) -> {len(out)} after removing duplicates") + ev
        return {"findings": out, "events": ev}

    def n_score(self, st: State):
        w = self.s.weights
        ev = []
        for f in st["findings"]:
            prox = 1.0 if f.distance_m is None else max(0.0, 1 - min(1.0, f.distance_m / (f.corridor_m or DEFAULT_CORRIDOR_M)))
            parts = {"severity": self.s.severity_weight[f.severity], "proximity": prox,
                     "basis": self.s.basis_weight[f.basis], "confidence": f.confidence}
            f.score_parts = {k: round(v, 3) for k, v in parts.items()}
            f.score = round(sum(w[k] * v for k, v in parts.items()), 3)
            ev += _ev("score", f"{f.title}: relevance {f.score}", key=f.key, parts=f.score_parts, weights=w)
        return {"findings": st["findings"], "events": ev}

    def n_decide(self, st: State):
        s, req = self.s, st["request"]
        routes = {r.id: r for r in req.routes}
        now = st["now"]
        decisions: list[Decision] = []
        alerts = 0
        for f in sorted(st["findings"], key=lambda x: -(x.score or 0)):
            reason = self._suppression(f, routes, req, now)
            if reason is None and alerts >= s.max_alerts_per_run:
                reason = f"over the limit of {s.max_alerts_per_run} alerts per run (lower priority)"
            if reason:
                decisions.append(Decision(key=f.key, action="suppress", reasons=[reason], finding=f))
                continue
            alerts += 1
            dist = f"{round(f.distance_m)} m from the route" if f.distance_m is not None else "affects the whole route"
            decisions.append(Decision(key=f.key, action="alert", rank=alerts, finding=f, reasons=[
                f"relevance {f.score} is above the {s.relevance_threshold} threshold",
                f"{f.severity} severity, {f.basis} ({'predicted from a model estimate' if f.basis == 'predicted' else 'not independently verified' if f.basis == 'reported' else 'official source'})",
                dist]))
        ev = [e for d in decisions for e in _ev("decide", f"{d.action.upper()}: {d.finding.title}", key=d.key, reasons=d.reasons)]
        return {"decisions": decisions, "events": ev}

    def _suppression(self, f: Finding, routes: dict[str, MonitoredRoute], req: RunRequest, now: datetime) -> str | None:
        if f.simulated and not req.include_simulated:
            return "simulated demo data is excluded from alerts"
        owners = [routes[r] for r in f.route_ids if r in routes]
        enabled = [r for r in owners if f.category in r.categories]
        if not enabled:
            return f"{f.category} alerts are turned off for this route"
        if not any(SEV_ORDER.index(f.severity) >= SEV_ORDER.index(r.min_severity) for r in enabled):
            return f"severity {f.severity} is below your minimum ({enabled[0].min_severity})"
        if (f.score or 0) < self.s.relevance_threshold:
            return f"relevance {f.score} is below the {self.s.relevance_threshold} threshold"
        last = self.store.last_alert(f.key)
        if last:
            sev, at = last
            at = at if at.tzinfo else at.replace(tzinfo=timezone.utc)
            if now - at < timedelta(hours=self.s.cooldown_hours) and SEV_ORDER.index(f.severity) <= SEV_ORDER.index(sev):
                return f"already alerted {_hours(now - at)} ago and it has not escalated (cooldown {self.s.cooldown_hours:g} h)"
        return None

    def n_record(self, st: State):
        decisions = st.get("decisions", [])
        alerts = [d for d in decisions if d.action == "alert"]
        suppressed = [d for d in decisions if d.action == "suppress"]
        summary = {"routes": len(st["request"].routes), "findings": len(st.get("findings", [])),
                   "alerts": len(alerts), "suppressed": len(suppressed), "degraded": st["degraded"],
                   "headline": _headline(alerts, st["degraded"], bool(st["trips"] or st["road"]),
                                      sum("already alerted" in d.reasons[0] for d in suppressed))}
        ev = list(st["events"]) + _ev("record", summary["headline"], **{k: summary[k] for k in ("alerts", "suppressed")})
        self.store.save_run(st["run_id"], st["now"], summary, ev, [d.model_dump(mode="json") for d in decisions])
        return {"summary": summary}


def _hours(td: timedelta) -> str:
    m = td.total_seconds() / 60
    return f"{round(m)} min" if m < 90 else f"{m / 60:.1f} h"


def _best_alt(plan: dict, prim: dict, min_saving_s: float) -> dict | None:
    best = None
    for r in plan["routes"]:
        if r["id"] == prim["id"] or any(w["kind"] == "closure" for w in r.get("warnings", [])):
            continue
        saves = prim["prediction"]["predicted_s"] - r["prediction"]["predicted_s"]
        if saves >= min_saving_s and (best is None or saves > best["saves_s"]):
            best = {"via": r["via"], "saves_s": saves, "id": r["id"]}
    return best


def _headline(alerts: list[Decision], degraded: list[str], any_data: bool, repeats: int = 0) -> str:
    if not any_data:
        return "No agent returned data, so nothing could be checked" + (f" ({', '.join(degraded)} unavailable)" if degraded else "")
    base = f"{len(alerts)} alert(s)" if alerts else (
        f"No new alerts ({repeats} already reported earlier)" if repeats else "Nothing needs your attention")
    return base + (f"; partial check, unavailable: {', '.join(dict.fromkeys(degraded))}" if degraded else "")
