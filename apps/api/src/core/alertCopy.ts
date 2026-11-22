import { AgentContract } from "./validate";

type Severity = "info" | "low" | "moderate" | "high" | "critical";

const TEMPLATES: Record<string, Record<Severity, (c: AgentContract, area: string) => string>> = {
  supply_disruption: {
    critical: (c, area) =>
      `Supply cut near ${area}. Expected duration: check BWSSB bulletin. Store water now. Emergency tanker helpline: 1916.`,
    high: (c, area) =>
      `Supply disruption near ${area}. Store water. Contact BWSSB on 1916 for updates. Tanker may be available at your ward office.`,
    moderate: (c, area) =>
      `Reduced supply near ${area}. Store water as a precaution. Check bwssb.gov.in for updates.`,
    low: (c, area) =>
      `Minor supply irregularity near ${area}. Monitor your taps. Likely resolved soon.`,
    info: (c, area) =>
      `Supply notice for ${area}. No action needed currently. Stay informed via BWSSB updates.`,
  },
  tanker_shortage: {
    critical: (c, area) =>
      `No tanker supply near ${area}. Contact ward tanker helpline: 080-22221111. Store available water immediately.`,
    high: (c, area) =>
      `Tanker shortage near ${area}. Call 080-22221111 for schedule. Store water.`,
    moderate: (c, area) =>
      `Tanker delayed near ${area}. Check updated schedule at your ward office or call 080-22221111.`,
    low: (c, area) =>
      `Tanker slightly delayed near ${area}. Expected within a few hours. Monitor the schedule.`,
    info: (c, area) =>
      `Tanker update for ${area}. No immediate action needed.`,
  },
  sensor_anomaly: {
    critical: (c, area) =>
      `Critical pressure drop detected near ${area}. Possible main pipe failure. Avoid heavy water use. Report to BWSSB: 1916.`,
    high: (c, area) =>
      `Significant pressure drop near ${area}. Possible pipe issue. Report to BWSSB: 1916 if taps are dry.`,
    moderate: (c, area) =>
      `Low water pressure near ${area}. Monitor your taps. May resolve in a few hours.`,
    low: (c, area) =>
      `Slight pressure variation near ${area}. No immediate action needed.`,
    info: (c, area) =>
      `Sensor reading noted for ${area}. Within acceptable range.`,
  },
  demand_spike: {
    critical: (c, area) =>
      `Very high water demand near ${area}. Supply may be severely reduced. Use stored water and avoid peak usage.`,
    high: (c, area) =>
      `High demand near ${area}. Supply may reduce during 2–5 PM. Use stored water if possible.`,
    moderate: (c, area) =>
      `Above-average demand near ${area}. Supply may be slightly reduced. Avoid peak usage 2–5 PM.`,
    low: (c, area) =>
      `Mild demand increase near ${area}. No action needed.`,
    info: (c, area) =>
      `Demand note for ${area}. Normal supply expected.`,
  },
};

export function buildAlertCopy(contract: AgentContract, areaName: string): string {
  const type = contract.incident_type as keyof typeof TEMPLATES;
  const severity = contract.severity as Severity;
  const area = areaName || "your area";

  const typeTemplates = TEMPLATES[type];
  if (!typeTemplates) {
    return `Water supply issue reported near ${area}. Check BWSSB updates or call 1916.`;
  }

  const fn = typeTemplates[severity];
  if (!fn) {
    return `Water supply issue reported near ${area}. Check BWSSB updates or call 1916.`;
  }

  const copy = fn(contract, area);
  const basis = contract.is_simulated
    ? " [Demo data]"
    : contract.verification_status === "confirmed"
    ? " [Confirmed]"
    : contract.verification_status === "reported"
    ? " [Community report]"
    : " [Predicted]";

  return copy + basis;
}
