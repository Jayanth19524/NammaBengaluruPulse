export interface Incident {
  id?: string;
  incident_type: string;
  latitude: number;
  longitude: number;
  severity: "info" | "low" | "moderate" | "high" | "critical";
  confidence: number;
  verification_status: "confirmed" | "reported" | "predicted";
  affected_route: boolean;
  evidence: string[];
  source: string[];
  recommended_action: string;
  area_name?: string;
  observed_at: string;
  is_simulated: boolean;
}

export interface ScanResult {
  incidents: Incident[];
  count: number;
}

export interface Notification {
  id: string;
  incident_id: string;
  alert_copy: string;
  category: string;
  severity: string;
  basis: string;
  is_read: boolean;
  created_at: string;
}
