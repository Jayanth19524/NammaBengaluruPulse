export type Severity = "info" | "low" | "moderate" | "high" | "critical";
export type Kind = "pothole" | "road_damage" | "closure" | "construction" | "other";
export type Basis = "confirmed" | "reported" | "predicted";
export const SEVERITIES: Severity[] = ["info", "low", "moderate", "high", "critical"];

export interface AgentResponse {
  agent: string; incident_id: string; incident_type: Kind;
  location: { latitude: number; longitude: number };
  severity: Severity; confidence: number; verification_status: Basis;
  affected_route: boolean; route_id: string | null; distance_m: number | null;
  evidence: Record<string, unknown>[]; source: string[]; recommended_action: string;
  observed_at: string; is_simulated: boolean;
}
export interface Incident {
  id: string; kind: Kind; latitude: number; longitude: number; severity: Severity;
  verification_status: Basis; repair_status: "open" | "repair_reported" | "repaired";
  first_seen: string; last_seen: string; report_count: number; description: string;
  sources: string[]; evidence: Record<string, unknown>[]; confidence: number; is_simulated: boolean;
}
export interface SourceHealth { source: string; status: "ok" | "degraded"; simulated?: boolean; error?: string }
export interface InvestigateResult {
  responses: AgentResponse[]; source_health: SourceHealth[];
  audit: { routes: number; active_incidents: number; relevant: number; at: string };
}
export interface Health { agent: string; city: string; detector: string; detector_available: boolean; adapters: { name: string; simulated: boolean }[] }
export interface ReportResult { incident: Incident; created: boolean; analysis: { cv_run: boolean; note: string; result?: string } }

/** One incident as the UI shows it: the stored incident plus route relevance when it applies. */
export interface Item {
  id: string; kind: Kind; lat: number; lon: number; severity: Severity; basis: Basis;
  confidence: number; distanceM: number | null; routeId: string | null; onRoute: boolean;
  action: string; evidence: Record<string, unknown>[]; sources: string[]; observedAt: string;
  simulated: boolean; repairStatus: Incident["repair_status"]; reportCount: number; description: string;
}

export interface Prediction { predicted_s: number; low_s: number; high_s: number; snapshot_s: number; free_flow_s: number; arrive_at: string; basis: string }
export interface TripWarning { kind: Kind; severity: Severity; basis: Basis; distance_m: number | null; simulated: boolean; action: string }
export interface PlannedRoute {
  id: string; geometry: [number, number][]; distance_m: number; prediction: Prediction; via: string[];
  warnings: TripWarning[]; recommended: boolean; delta_vs_best_s: number; incidents_on_route: number;
}
export interface DepartureOption { depart_at: string; predicted_s: number; arrive_at: string }
export interface TripPlan {
  routes: PlannedRoute[]; departure_options: DepartureOption[]; road_incidents: string; profile: string; live_traffic: string | null;
}
