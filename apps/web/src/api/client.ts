import { DEMO_ROUTES } from "../demo";
import type { Health, Incident, InvestigateResult, Item, ReportResult } from "./types";

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let msg = `${res.status}`;
    try { msg = (await res.json()).detail ?? msg; } catch { /* keep status */ }
    throw new Error(String(msg));
  }
  return res.json();
}

export const getHealth = () => fetch("/api/health").then((r) => json<Health>(r));
export const getIncidents = () => fetch("/api/incidents").then((r) => json<Incident[]>(r));
export const investigate = () =>
  fetch("/api/investigate", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ routes: DEMO_ROUTES }),
  }).then((r) => json<InvestigateResult>(r));

export interface ReportInput { lat: number; lon: number; kind: string; severity: string; description: string; image: File | null }

export function reporterId(): string {
  try {
    let id = localStorage.getItem("np_reporter");
    if (!id) { id = crypto.randomUUID(); localStorage.setItem("np_reporter", id); }
    return id;
  } catch { return "anonymous-session"; }
}

export function postReport(i: ReportInput) {
  const f = new FormData();
  f.set("lat", String(i.lat)); f.set("lon", String(i.lon)); f.set("kind", i.kind);
  f.set("severity", i.severity); f.set("description", i.description); f.set("reporter_id", reporterId());
  if (i.image) f.set("image", i.image);
  return fetch("/api/reports", { method: "POST", body: f }).then((r) => json<ReportResult>(r));
}

const DEFAULT_ACTION = "Not on your monitored routes. Check it if you plan to travel this stretch.";

export function buildItems(incidents: Incident[], inv: InvestigateResult | undefined): Item[] {
  const byId = new Map((inv?.responses ?? []).map((r) => [r.incident_id, r]));
  return incidents.map((i) => {
    const r = byId.get(i.id);
    return {
      id: i.id, kind: i.kind, lat: i.latitude, lon: i.longitude, severity: i.severity,
      basis: i.verification_status, confidence: i.confidence,
      distanceM: r?.distance_m ?? null, routeId: r?.route_id ?? null, onRoute: !!r,
      action: r?.recommended_action ?? DEFAULT_ACTION,
      evidence: r?.evidence ?? i.evidence, sources: i.sources, observedAt: i.last_seen,
      simulated: i.is_simulated, repairStatus: i.repair_status, reportCount: i.report_count,
      description: i.description,
    };
  });
}
