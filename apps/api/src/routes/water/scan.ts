import { Router, Request, Response } from "express";
import { callWaterWatchAgent } from "../../core/agentProxy";
import { validateAgentContracts, AgentContract } from "../../core/validate";
import { pool } from "../../db/pool";
import { reverseGeocode } from "../../core/reverseGeocode";
import { createNotification } from "../../core/notifications";
import { log } from "../../core/logger";

export const scanRouter = Router();

scanRouter.post("/", async (req: Request, res: Response) => {
  const { lat, lng, radius } = req.body as {
    lat?: unknown;
    lng?: unknown;
    radius?: unknown;
  };

  if (typeof lat !== "number" || typeof lng !== "number") {
    return res.status(400).json({ error: "lat and lng must be numbers" });
  }
  if (lat < -90 || lat > 90 || lng < -180 || lng > 180) {
    return res.status(400).json({ error: "lat/lng out of range" });
  }
  const radiusM = typeof radius === "number" ? Math.min(radius, 50000) : 5000;

  log("info", "[scan] request received", { lat, lng, radius: radiusM });

  let contracts: AgentContract[];
  try {
    const agentResp = await callWaterWatchAgent({
      latitude: lat,
      longitude: lng,
      radius_m: radiusM,
    });
    contracts = validateAgentContracts(agentResp.incidents);
  } catch (err: unknown) {
    log("error", "[scan] agent call failed", { err: String(err) });
    return res.status(502).json({ error: "Water agent unavailable", detail: String(err) });
  }

  // Persist each incident + generate notification
  const savedIncidents = [];
  for (const contract of contracts) {
    const areaName = contract.incident_type
      ? (contract as unknown as { area_name?: string }).area_name ?? ""
      : "";

    // Reverse geocode if no area name provided
    const resolvedArea =
      areaName || (await reverseGeocode(contract.location.latitude, contract.location.longitude));

    try {
      const { rows } = await pool.query(
        `INSERT INTO water_incidents
          (incident_type, geom, severity, confidence, verification_status,
           affected_route, evidence, source, recommended_action, area_name,
           observed_at, expires_at, is_simulated)
         VALUES ($1,
           ST_SetSRID(ST_MakePoint($2, $3), 4326)::geography,
           $4, $5, $6, $7, $8, $9, $10, $11, $12,
           NOW() + INTERVAL '48 hours',
           $13)
         ON CONFLICT DO NOTHING
         RETURNING id`,
        [
          contract.incident_type,
          contract.location.longitude,
          contract.location.latitude,
          contract.severity,
          contract.confidence,
          contract.verification_status,
          contract.affected_route,
          contract.evidence,
          contract.source,
          contract.recommended_action,
          resolvedArea,
          new Date(contract.observed_at),
          contract.is_simulated,
        ]
      );

      const incidentId = rows[0]?.id as string | undefined;
      if (incidentId) {
        await createNotification(incidentId, contract, resolvedArea);
        savedIncidents.push({ ...contract, id: incidentId, area_name: resolvedArea });
      }
    } catch (dbErr: unknown) {
      log("error", "[scan] DB insert failed", { err: String(dbErr) });
    }
  }

  return res.json({ incidents: savedIncidents, count: savedIncidents.length });
});
