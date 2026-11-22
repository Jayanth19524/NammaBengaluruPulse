-- Migration 003: Sensor readings table

CREATE TABLE IF NOT EXISTS sensor_readings (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  device_id    TEXT NOT NULL,
  geom         GEOGRAPHY(Point, 4326) NOT NULL,
  value        NUMERIC NOT NULL,
  unit         TEXT NOT NULL,              -- e.g. "bar", "litres/min", "ppm"
  reading_type TEXT NOT NULL,             -- e.g. "pressure", "flow_rate", "quality"
  is_simulated BOOLEAN NOT NULL DEFAULT FALSE,
  recorded_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS sensor_readings_geom_idx
  ON sensor_readings USING GIST (geom);

CREATE INDEX IF NOT EXISTS sensor_readings_device_id_idx
  ON sensor_readings (device_id);

CREATE INDEX IF NOT EXISTS sensor_readings_recorded_at_idx
  ON sensor_readings (recorded_at DESC);
