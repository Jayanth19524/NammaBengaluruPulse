from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import httpx

from .models import DepartureOption, PlannedRoute
from .predictor import Predictor
from .routing import OsrmRouter


class RoadIncidents:
    """Asks the RoadTrust agent which incidents lie along each candidate route."""

    def __init__(self, base_url: str, client: httpx.Client | None = None, timeout: float = 8.0):
        self.base, self._client, self.timeout = base_url.rstrip("/"), client, timeout

    def along(self, routes: dict[str, list[tuple[float, float]]]) -> dict[str, list[dict]] | None:
        try:
            client = self._client or httpx.Client(timeout=self.timeout)
            body = {"routes": [{"id": rid, "geometry": _thin(g)} for rid, g in routes.items()]}
            r = client.post(f"{self.base}/investigate", json=body)
            r.raise_for_status()
            out: dict[str, list[dict]] = {rid: [] for rid in routes}
            for resp in r.json()["responses"]:
                out.setdefault(resp["route_id"], []).append(resp)
            return out
        except (httpx.HTTPError, ValueError, KeyError):
            return None  # RoadTrust unavailable: say so rather than imply "no incidents"


def _thin(geom: list[tuple[float, float]], max_pts: int = 400) -> list[tuple[float, float]]:
    if len(geom) <= max_pts:
        return geom
    step = len(geom) / max_pts
    return [geom[int(i * step)] for i in range(max_pts)] + [geom[-1]]


class Planner:
    def __init__(self, router: OsrmRouter, predictor: Predictor, incidents: RoadIncidents | None = None,
                 tz: str = "Asia/Kolkata"):
        self.router, self.predictor, self.incidents = router, predictor, incidents
        self.tz = ZoneInfo(tz)  # the profile is defined in the city's local time

    def local(self, t: datetime | None) -> datetime:
        if t is None:
            return datetime.now(self.tz)
        return t.replace(tzinfo=self.tz) if t.tzinfo is None else t.astimezone(self.tz)

    def plan(self, origin, dest, depart_at: datetime | None = None, check_incidents: bool = True) -> dict:
        now = self.local(None)
        depart = self.local(depart_at) if depart_at else now
        candidates = self.router.routes(origin, dest)
        planned: list[PlannedRoute] = []
        for i, c in enumerate(candidates):
            pred = self.predictor.predict(c, depart, now=now)
            via = _via(c)
            planned.append(PlannedRoute(id=f"route-{i + 1}", geometry=c.geometry, distance_m=round(c.distance_m),
                                        prediction=pred, via=via))
        road_note = "not checked"
        if check_incidents and self.incidents:
            found = self.incidents.along({p.id: p.geometry for p in planned})
            if found is None:
                road_note = "RoadTrust unavailable, road incidents not checked"
            else:
                road_note = "checked"
                for p in planned:
                    p.warnings = [_warning(w) for w in found.get(p.id, [])]
                    p.incidents_on_route = len(p.warnings)
        # A route with a reported closure is not recommended even if it is the fastest.
        def blocked(p: PlannedRoute) -> bool:
            return any(w["kind"] == "closure" for w in p.warnings)
        planned.sort(key=lambda p: (blocked(p), p.prediction.predicted_s))
        best = planned[0].prediction.predicted_s
        for p in planned:
            p.delta_vs_best_s = p.prediction.predicted_s - best
        planned[0].recommended = True
        return {"routes": planned, "departure_options": self.departure_options(candidates[0], depart, now),
                "road_incidents": road_note, "profile": self.predictor.profile.source,
                "live_traffic": self.predictor.live.name if self.predictor.live else None}

    def departure_options(self, route, depart: datetime, now: datetime) -> list[DepartureOption]:
        out = []
        for offset in (-30, -15, 0, 15, 30, 45, 60):
            d = depart + timedelta(minutes=offset)
            if d < now - timedelta(minutes=1):
                continue  # cannot leave in the past
            p = self.predictor.predict(route, d, now=now)
            out.append(DepartureOption(depart_at=d, predicted_s=p.predicted_s, arrive_at=p.arrive_at))
        return out


def _via(c) -> list[str]:
    """The longest named roads on the route, by distance."""
    dist: dict[str, float] = {}
    for s in c.steps:
        if s.name:
            dist[s.name] = dist.get(s.name, 0) + s.distance_m
    return [n for n, _ in sorted(dist.items(), key=lambda kv: -kv[1])[:2]]


def _warning(w: dict) -> dict:
    return {"kind": w["incident_type"], "severity": w["severity"], "basis": w["verification_status"],
            "distance_m": w.get("distance_m"), "simulated": w.get("is_simulated", False),
            "action": w["recommended_action"], "location": w["location"]}
