"""Real road routes with alternatives from OSRM (OpenStreetMap data). OSRM durations are
free-flow: they contain no traffic, which is exactly why the predictor exists."""
from __future__ import annotations

import httpx

from .models import CandidateRoute, Step

OSRM_URL = "https://router.project-osrm.org"


class RoutingError(Exception):
    pass


class OsrmRouter:
    def __init__(self, base: str = OSRM_URL, client: httpx.Client | None = None, timeout: float = 15.0):
        self.base, self._client, self.timeout = base, client, timeout

    def routes(self, origin: tuple[float, float], dest: tuple[float, float], alternatives: int = 3) -> list[CandidateRoute]:
        (olat, olon), (dlat, dlon) = origin, dest
        url = f"{self.base}/route/v1/driving/{olon},{olat};{dlon},{dlat}"
        params = {"alternatives": str(alternatives), "overview": "full", "geometries": "geojson", "steps": "true"}
        try:
            client = self._client or httpx.Client(timeout=self.timeout)
            resp = client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise RoutingError(f"Routing service unavailable: {exc}") from exc
        if data.get("code") != "Ok":
            raise RoutingError(f"No route found ({data.get('code')})")
        out = []
        for r in data["routes"]:
            steps = []
            for leg in r["legs"]:
                for st in leg["steps"]:
                    if st["duration"] <= 0 and st["distance"] <= 0:
                        continue
                    coords = st["geometry"]["coordinates"]
                    mid = tuple(coords[len(coords) // 2]) if coords else None
                    steps.append(Step(free_flow_s=st["duration"], distance_m=st["distance"], name=st.get("name", ""), mid=mid))
            out.append(CandidateRoute(steps=steps, geometry=[tuple(c) for c in r["geometry"]["coordinates"]]))
        return out
