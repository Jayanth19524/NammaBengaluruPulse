import { pool } from "../db/pool";
import { AgentContract } from "./validate";
import { buildAlertCopy } from "./alertCopy";
import { log } from "./logger";

export interface StoredNotification {
  id: string;
  incident_id: string;
  alert_copy: string;
  category: string;
  severity: string;
  basis: string;
  is_read: boolean;
  created_at: string;
}

export async function createNotification(
  incidentId: string,
  contract: AgentContract,
  areaName: string
): Promise<StoredNotification | null> {
  // Dedup — one notification per incident
  const { rows: existing } = await pool.query(
    "SELECT id FROM notifications WHERE incident_id = $1",
    [incidentId]
  );
  if (existing.length > 0) return null;

  const alertCopy = buildAlertCopy(contract, areaName);
  const basis = contract.is_simulated
    ? "simulated"
    : contract.verification_status;

  const { rows } = await pool.query<StoredNotification>(
    `INSERT INTO notifications (incident_id, alert_copy, category, severity, basis)
     VALUES ($1, $2, 'water', $3, $4)
     RETURNING id, incident_id, alert_copy, category, severity, basis, is_read, created_at::text`,
    [incidentId, alertCopy, contract.severity, basis]
  );

  log("info", "[notifications] created notification", { incidentId });
  return rows[0] ?? null;
}

export async function getRecentNotifications(limit = 20): Promise<StoredNotification[]> {
  const { rows } = await pool.query<StoredNotification>(
    `SELECT id, incident_id, alert_copy, category, severity, basis, is_read, created_at::text
     FROM notifications
     ORDER BY created_at DESC
     LIMIT $1`,
    [limit]
  );
  return rows;
}

export async function markRead(notificationId: string): Promise<void> {
  await pool.query("UPDATE notifications SET is_read = TRUE WHERE id = $1", [
    notificationId,
  ]);
}
