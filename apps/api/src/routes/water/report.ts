import { Router, Request, Response } from "express";
import { pool } from "../../db/pool";
import { log } from "../../core/logger";

export const reportRouter = Router();

reportRouter.post("/", async (req: Request, res: Response) => {
  const { lat, lng, description } = req.body as {
    lat?: unknown;
    lng?: unknown;
    description?: unknown;
  };

  if (typeof lat !== "number" || typeof lng !== "number") {
    return res.status(400).json({ error: "lat and lng must be numbers" });
  }
  if (typeof description !== "string" || description.trim().length < 5) {
    return res.status(400).json({ error: "description must be at least 5 characters" });
  }

  log("info", "[report] community report received", { lat, lng });

  const { rows } = await pool.query(
    `INSERT INTO water_incidents
      (incident_type, geom, severity, confidence, verification_status,
       affected_route, evidence, source, recommended_action,
       observed_at, expires_at, is_simulated)
     VALUES (
       'supply_disruption',
       ST_SetSRID(ST_MakePoint($2, $1), 4326)::geography,
       'low', 0.4, 'reported',
       false,
       ARRAY[$3],
       ARRAY['community_report'],
       'Community report received. BWSSB has been notified. Call 1916 for status.',
       NOW(), NOW() + INTERVAL '24 hours', FALSE
     )
     RETURNING id`,
    [lat, lng, description.trim()]
  );

  return res.status(201).json({ id: rows[0]?.id, message: "Report submitted" });
});
