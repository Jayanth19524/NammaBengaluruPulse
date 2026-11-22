-- Migration 005: Notifications table

CREATE TABLE IF NOT EXISTS notifications (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  incident_id   UUID NOT NULL REFERENCES water_incidents(id) ON DELETE CASCADE,
  alert_copy    TEXT NOT NULL,
  category      TEXT NOT NULL DEFAULT 'water',
  severity      TEXT NOT NULL,
  basis         TEXT NOT NULL CHECK (basis IN ('confirmed', 'reported', 'predicted', 'simulated')),
  is_read       BOOLEAN NOT NULL DEFAULT FALSE,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (incident_id)   -- one notification per incident (dedup)
);

CREATE INDEX IF NOT EXISTS notifications_created_at_idx
  ON notifications (created_at DESC);

CREATE INDEX IF NOT EXISTS notifications_is_read_idx
  ON notifications (is_read);
