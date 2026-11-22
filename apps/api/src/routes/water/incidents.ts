import { Router, Request, Response } from "express";
import { pool } from "../../db/pool";
import { log } from "../../core/logger";

export const incidentsRouter = Router();

incidentsRouter.get("/", async (req: Request, res: Response) => {
  const lat = parseFloat(req.query.lat as string);
  const lng = parseFloat(req.query.lng as string);
  const radius = parseFloat((req.query.radius as string) ?? "5000");

  if (isNaN(lat) || isNaN(lng)) {
    return res.status(400).json({ error: "lat and lng query params are required" });
  }

  log("info", "[incidents] query", { lat, lng, radius });

  const { rows } = await pool.query(
    `SELECT
       id, incident_type,
       ST_Y(geom::geometry) AS latitude,
       ST_X(geom::geometry) AS longitude,
       severity, confidence, verification_status,
       affected_route, evidence, source, recommended_action,
       area_name, observed_at, expires_at, is_simulated, created_at
     FROM water_incidents
     WHERE ST_DWithin(geom, ST_SetSRID(ST_MakePoint($2, $1), 4326)::geography, $3)
       AND (expires_at IS NULL OR expires_at > NOW())
     ORDER BY
       CASE severity
         WHEN 'critical' THEN 1
         WHEN 'high' THEN 2
         WHEN 'moderate' THEN 3
         WHEN 'low' THEN 4
         ELSE 5
       END,
       observed_at DESC
     LIMIT 50`,
    [lat, lng, radius]
  );

  return res.json({ incidents: rows, count: rows.length });
});
