-- Migration 004: Agent investigations audit log

CREATE TABLE IF NOT EXISTS agent_investigations (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  agent        TEXT NOT NULL CHECK (agent IN ('FloodLens', 'RoadTrust', 'WaterWatch')),
  scan_lat     NUMERIC NOT NULL,
  scan_lng     NUMERIC NOT NULL,
  radius_m     INTEGER NOT NULL,
  adapter_used TEXT NOT NULL,
  incident_count INTEGER NOT NULL DEFAULT 0,
  duration_ms  INTEGER,
  error        TEXT,
  is_simulated BOOLEAN NOT NULL DEFAULT FALSE,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS agent_investigations_agent_idx
  ON agent_investigations (agent);

CREATE INDEX IF NOT EXISTS agent_investigations_created_at_idx
  ON agent_investigations (created_at DESC);
