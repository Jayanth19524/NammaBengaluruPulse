"""Agent execution log: structured, in-memory log of every investigation step.

Every step the RoadTrust agent takes is recorded here as a timestamped event.
The SSE endpoint in api.py streams these to the UI so users can see the agent
working in real time.

Events have:
  kind:    "start" | "adapter_fetch" | "adapter_ok" | "adapter_error"
         | "dedup" | "geo_check" | "result" | "done" | "report_submitted"
  message: human-readable plain sentence
  data:    optional structured payload
  at:      ISO-8601 timestamp
"""
from __future__ import annotations

import json
import threading
from collections import deque
from datetime import datetime, timezone
from typing import Any


class AgentLog:
    """Thread-safe ring buffer of agent execution events, with SSE fan-out."""

    MAX_EVENTS = 200

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._events: deque[dict] = deque(maxlen=self.MAX_EVENTS)
        self._listeners: list[threading.Event] = []

    # -- writing -----------------------------------------------------------

    def _emit(self, kind: str, message: str, data: dict | None = None) -> None:
        event = {
            "kind": kind,
            "message": message,
            "data": data or {},
            "at": datetime.now(timezone.utc).isoformat(),
        }
        with self._lock:
            self._events.append(event)
            # wake all SSE listeners
            for ev in self._listeners:
                ev.set()

    def start(self, routes: int) -> None:
        self._emit("start", f"Investigation started — checking {routes} route{'s' if routes != 1 else ''}.",
                   {"routes": routes})

    def adapter_fetch(self, name: str, bbox: tuple) -> None:
        self._emit("adapter_fetch", f"Fetching from {name}…",
                   {"source": name, "bbox": list(bbox)})

    def adapter_ok(self, name: str, count: int, simulated: bool) -> None:
        label = " (demo data)" if simulated else ""
        self._emit("adapter_ok", f"{name}{label} — {count} record{'s' if count != 1 else ''} returned.",
                   {"source": name, "count": count, "simulated": simulated})

    def adapter_error(self, name: str, error: str) -> None:
        self._emit("adapter_error", f"{name} unavailable — continuing with other sources. ({error})",
                   {"source": name, "error": error})

    def dedup(self, created: int, merged: int) -> None:
        self._emit("dedup", f"Deduplication: {created} new incident{'s' if created != 1 else ''}, "
                            f"{merged} merged with existing.",
                   {"created": created, "merged": merged})

    def geo_check(self, route_id: str, corridor_m: float, active: int, relevant: int) -> None:
        self._emit("geo_check",
                   f"Route {route_id}: {active} active incident{'s' if active != 1 else ''} checked "
                   f"against {corridor_m:.0f} m corridor — {relevant} within range.",
                   {"route_id": route_id, "corridor_m": corridor_m,
                    "active": active, "relevant": relevant})

    def result(self, relevant: int) -> None:
        self._emit("result",
                   f"{relevant} incident{'s' if relevant != 1 else ''} relevant to your routes.",
                   {"relevant": relevant})

    def done(self) -> None:
        self._emit("done", "Investigation complete.")

    def report_submitted(self, kind: str, lat: float, lon: float, cv_run: bool,
                         cv_result: str | None, created: bool) -> None:
        cv_note = ""
        if cv_run:
            cv_note = f" CV: {cv_result}." if cv_result else " CV: no damage found."
        merge_note = "New incident created." if created else "Merged with an existing nearby report."
        self._emit("report_submitted",
                   f"Community report received: {kind} at ({lat:.5f}, {lon:.5f}).{cv_note} {merge_note}",
                   {"kind": kind, "lat": lat, "lon": lon,
                    "cv_run": cv_run, "created": created})

    # -- reading (SSE) -----------------------------------------------------

    def snapshot(self) -> list[dict]:
        with self._lock:
            return list(self._events)

    def sse_stream(self, after_index: int = -1):
        """Generator that yields SSE-formatted strings.
        Yields all buffered events after `after_index` first, then blocks until
        new events arrive. The caller iterates this inside a streaming response.
        """
        listener = threading.Event()
        with self._lock:
            self._listeners.append(listener)
        try:
            sent = 0
            # replay history
            snapshot = self.snapshot()
            start = max(0, after_index + 1)
            for ev in snapshot[start:]:
                yield _sse(ev)
                sent += 1
            last_len = len(snapshot)
            # stream live
            while True:
                listener.wait(timeout=25)
                listener.clear()
                current = self.snapshot()
                for ev in current[last_len:]:
                    yield _sse(ev)
                last_len = len(current)
                # keepalive ping so the browser doesn't time out
                yield ": ping\n\n"
        finally:
            with self._lock:
                try:
                    self._listeners.remove(listener)
                except ValueError:
                    pass


def _sse(event: dict) -> str:
    return f"data: {json.dumps(event)}\n\n"


# Module-level singleton shared by the whole process
log = AgentLog()
