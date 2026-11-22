-- Migration 002: Water incidents table

CREATE TABLE IF NOT EXISTS water_incidents (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  incident_type       TEXT NOT NULL CHECK (incident_type IN (
                        'supply_disruption', 'tanker_shortage',
                        'sensor_anomaly', 'demand_spike'
                      )),
  geom                GEOGRAPHY(Point, 4326) NOT NULL,
  severity            TEXT NOT NULL CHECK (severity IN (
                        'info', 'low', 'moderate', 'high', 'critical'
                      )),
  confidence          NUMERIC(4,3) NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
  verification_status TEXT NOT NULL CHECK (verification_status IN (
                        'confirmed', 'reported', 'predicted'
                      )),
  affected_route      BOOLEAN NOT NULL DEFAULT FALSE,
  evidence            TEXT[]  NOT NULL DEFAULT '{}',
  source              TEXT[]  NOT NULL DEFAULT '{}',
  recommended_action  TEXT    NOT NULL,
  area_name           TEXT,                   -- reverse-geocoded neighbourhood name
  observed_at         TIMESTAMPTZ NOT NULL,
  expires_at          TIMESTAMPTZ,
  is_simulated        BOOLEAN NOT NULL DEFAULT FALSE,
  created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS water_incidents_geom_idx
  ON water_incidents USING GIST (geom);

CREATE INDEX IF NOT EXISTS water_incidents_severity_idx
  ON water_incidents (severity);

CREATE INDEX IF NOT EXISTS water_incidents_observed_at_idx
  ON water_incidents (observed_at DESC);

CREATE INDEX IF NOT EXISTS water_incidents_expires_at_idx
  ON water_incidents (expires_at);
