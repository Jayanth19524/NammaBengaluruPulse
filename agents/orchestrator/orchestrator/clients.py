"""Tool clients for the specialised agents. The orchestrator only talks to these interfaces."""
from __future__ import annotations

from datetime import datetime
from typing import Protocol

import httpx


class AgentUnavailable(Exception):
    pass


class TripClient(Protocol):
    def plan(self, origin: tuple[float, float], dest: tuple[float, float], depart_at: datetime | None) -> dict: ...


class RoadClient(Protocol):
    def investigate(self, routes: list[dict]) -> dict: ...


def _post(client: httpx.Client | None, url: str, body: dict, timeout: float) -> dict:
    try:
        c = client or httpx.Client(timeout=timeout)
        r = c.post(url, json=body)
        r.raise_for_status()
        return r.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise AgentUnavailable(str(exc)) from exc


class HttpTripClient:
    def __init__(self, base: str, client: httpx.Client | None = None, timeout: float = 45.0):
        self.base, self._client, self.timeout = base.rstrip("/"), client, timeout

    def plan(self, origin, dest, depart_at):
        body = {"origin": list(origin), "destination": list(dest),
                "depart_at": depart_at.isoformat() if depart_at else None,
                "check_incidents": False}  # the orchestrator asks RoadTrust itself, once
        return _post(self._client, f"{self.base}/plan", body, self.timeout)


class HttpRoadClient:
    def __init__(self, base: str, client: httpx.Client | None = None, timeout: float = 30.0):
        self.base, self._client, self.timeout = base.rstrip("/"), client, timeout

    def investigate(self, routes):
        return _post(self._client, f"{self.base}/investigate", {"routes": routes}, self.timeout)
