-- RoadTrust tables. DRAFT: not yet run against a real PostGIS instance.
-- Depends on the shared Phase 0 base tables; the minimal versions below are guarded
-- with IF NOT EXISTS so the Phase 0 owners can replace them.
CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE IF NOT EXISTS infrastructure_incidents (
  id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  agent               text NOT NULL CHECK (agent IN ('FloodLens','RoadTrust','WaterWatch')),
  category            text NOT NULL,
  geom                geometry(Point, 4326) NOT NULL,
  severity            text NOT NULL CHECK (severity IN ('info','low','moderate','high','critical')),
  verification_status text NOT NULL CHECK (verification_status IN ('confirmed','reported','predicted')),
  confidence          real NOT NULL CHECK (confidence BETWEEN 0 AND 1),
  is_simulated        boolean NOT NULL DEFAULT false,
  first_seen          timestamptz NOT NULL,
  last_seen           timestamptz NOT NULL,
  expires_at          timestamptz,
  created_at          timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS infrastructure_incidents_geom_gix ON infrastructure_incidents USING gist (geom);

CREATE TABLE IF NOT EXISTS incident_evidence (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  incident_id uuid NOT NULL REFERENCES infrastructure_incidents(id) ON DELETE CASCADE,
  type        text NOT NULL,
  payload     jsonb NOT NULL DEFAULT '{}',
  image_key   text,           -- object-storage key; EXIF stripped before public display
  source      text NOT NULL,
  created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS road_incidents (
  incident_id   uuid PRIMARY KEY REFERENCES infrastructure_incidents(id) ON DELETE CASCADE,
  kind          text NOT NULL CHECK (kind IN ('pothole','road_damage','closure','construction','other')),
  repair_status text NOT NULL DEFAULT 'open' CHECK (repair_status IN ('open','repair_reported','repaired')),
  report_count  integer NOT NULL DEFAULT 1,
  description   text NOT NULL DEFAULT '',
  osm_way_id    bigint
);
CREATE INDEX IF NOT EXISTS road_incidents_kind_idx ON road_incidents (kind, repair_status);

-- Reporter identities are stored hashed and kept out of API responses.
CREATE TABLE IF NOT EXISTS road_incident_reporters (
  incident_id uuid NOT NULL REFERENCES road_incidents(incident_id) ON DELETE CASCADE,
  reporter_hash text NOT NULL,
  reported_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (incident_id, reporter_hash)
);

CREATE TABLE IF NOT EXISTS road_repair_events (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  incident_id uuid NOT NULL REFERENCES road_incidents(incident_id) ON DELETE CASCADE,
  status      text NOT NULL CHECK (status IN ('open','repair_reported','repaired')),
  source      text NOT NULL,
  official    boolean NOT NULL,
  at          timestamptz NOT NULL
);
