"""SQLite persistence: run history, the decision log (audit trail) and alert history."""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY, at TEXT NOT NULL, summary TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS events (run_id TEXT NOT NULL, seq INTEGER NOT NULL, node TEXT NOT NULL,
  level TEXT NOT NULL, message TEXT NOT NULL, data TEXT NOT NULL, PRIMARY KEY (run_id, seq));
CREATE TABLE IF NOT EXISTS decisions (run_id TEXT NOT NULL, key TEXT NOT NULL, action TEXT NOT NULL,
  rank INTEGER, reasons TEXT NOT NULL, finding TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS alerts (key TEXT NOT NULL, run_id TEXT NOT NULL, severity TEXT NOT NULL,
  alerted_at TEXT NOT NULL, payload TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS alerts_key ON alerts (key, alerted_at);
"""


class Store:
    def __init__(self, path: str = ":memory:"):
        self.path = path
        self._keep = sqlite3.connect(path, check_same_thread=False) if path == ":memory:" else None
        with self._conn() as c:
            c.executescript(SCHEMA)

    @contextmanager
    def _conn(self):
        """One shared connection for :memory:, otherwise a short-lived connection per operation."""
        c = self._keep or sqlite3.connect(self.path)
        try:
            yield c
        finally:
            if self._keep is None:
                c.close()

    def last_alert(self, key: str) -> tuple[str, datetime] | None:
        with self._conn() as c:
            row = c.execute("SELECT severity, alerted_at FROM alerts WHERE key=? ORDER BY alerted_at DESC LIMIT 1", (key,)).fetchone()
        return (row[0], datetime.fromisoformat(row[1])) if row else None

    def save_run(self, run_id: str, at: datetime, summary: dict, events: list[dict], decisions: list[dict]) -> None:
        with self._conn() as c:
            c.execute("INSERT INTO runs VALUES (?,?,?)", (run_id, at.isoformat(), json.dumps(summary)))
            c.executemany("INSERT INTO events VALUES (?,?,?,?,?,?)",
                          [(run_id, i, e["node"], e["level"], e["message"], json.dumps(e["data"], default=str)) for i, e in enumerate(events)])
            for d in decisions:
                c.execute("INSERT INTO decisions VALUES (?,?,?,?,?,?)",
                          (run_id, d["key"], d["action"], d["rank"], json.dumps(d["reasons"]), json.dumps(d["finding"], default=str)))
                if d["action"] == "alert":
                    c.execute("INSERT INTO alerts VALUES (?,?,?,?,?)",
                              (d["key"], run_id, d["finding"]["severity"], at.isoformat(), json.dumps(d["finding"], default=str)))
            c.commit()

    def list_runs(self, limit: int = 20) -> list[dict]:
        with self._conn() as c:
            rows = c.execute("SELECT id, at, summary FROM runs ORDER BY at DESC LIMIT ?", (limit,)).fetchall()
        return [{"id": r[0], "at": r[1], **json.loads(r[2])} for r in rows]

    def get_run(self, run_id: str) -> dict | None:
        with self._conn() as c:
            run = c.execute("SELECT id, at, summary FROM runs WHERE id=?", (run_id,)).fetchone()
            if not run:
                return None
            ev = c.execute("SELECT node, level, message, data FROM events WHERE run_id=? ORDER BY seq", (run_id,)).fetchall()
            de = c.execute("SELECT key, action, rank, reasons, finding FROM decisions WHERE run_id=? ORDER BY rank IS NULL, rank", (run_id,)).fetchall()
        return {"id": run[0], "at": run[1], "summary": json.loads(run[2]),
                "events": [{"node": e[0], "level": e[1], "message": e[2], "data": json.loads(e[3])} for e in ev],
                "decisions": [{"key": d[0], "action": d[1], "rank": d[2], "reasons": json.loads(d[3]), "finding": json.loads(d[4])} for d in de]}

    def alert_history(self, limit: int = 50) -> list[dict]:
        with self._conn() as c:
            rows = c.execute("SELECT key, run_id, severity, alerted_at, payload FROM alerts ORDER BY alerted_at DESC LIMIT ?", (limit,)).fetchall()
        return [{"key": r[0], "run_id": r[1], "severity": r[2], "alerted_at": r[3], "finding": json.loads(r[4])} for r in rows]
