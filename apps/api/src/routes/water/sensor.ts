import { Router, Request, Response } from "express";
import { pool } from "../../db/pool";

export const sensorRouter = Router();

sensorRouter.get("/:deviceId", async (req: Request, res: Response) => {
  const { deviceId } = req.params;
  const limit = Math.min(parseInt((req.query.limit as string) ?? "20"), 100);

  const { rows } = await pool.query(
    `SELECT id, device_id,
       ST_Y(geom::geometry) AS latitude,
       ST_X(geom::geometry) AS longitude,
       value, unit, reading_type, is_simulated, recorded_at
     FROM sensor_readings
     WHERE device_id = $1
     ORDER BY recorded_at DESC
     LIMIT $2`,
    [deviceId, limit]
  );

  return res.json({ device_id: deviceId, readings: rows });
});

// Accept telemetry from ESP32 devices
sensorRouter.post("/telemetry", async (req: Request, res: Response) => {
  const { device_id, lat, lng, value, unit, reading_type, is_simulated } =
    req.body as {
      device_id?: string;
      lat?: number;
      lng?: number;
      value?: number;
      unit?: string;
      reading_type?: string;
      is_simulated?: boolean;
    };

  if (!device_id || typeof lat !== "number" || typeof lng !== "number" ||
      typeof value !== "number" || !unit || !reading_type) {
    return res.status(400).json({ error: "Missing required fields" });
  }

  await pool.query(
    `INSERT INTO sensor_readings (device_id, geom, value, unit, reading_type, is_simulated)
     VALUES ($1, ST_SetSRID(ST_MakePoint($3, $2), 4326)::geography, $4, $5, $6, $7)`,
    [device_id, lat, lng, value, unit, reading_type, is_simulated ?? false]
  );

  return res.status(201).json({ message: "Telemetry recorded" });
});
