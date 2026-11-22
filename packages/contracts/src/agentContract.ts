import { z } from "zod";

export const SeveritySchema = z.enum([
  "info",
  "low",
  "moderate",
  "high",
  "critical",
]);

export const VerificationStatusSchema = z.enum([
  "confirmed",
  "reported",
  "predicted",
]);

export const AgentNameSchema = z.enum([
  "FloodLens",
  "RoadTrust",
  "WaterWatch",
]);

export const WaterIncidentTypeSchema = z.enum([
  "supply_disruption",
  "tanker_shortage",
  "sensor_anomaly",
  "demand_spike",
]);

export const LocationSchema = z.object({
  latitude: z.number().min(-90).max(90),
  longitude: z.number().min(-180).max(180),
});

export const AgentContractSchema = z.object({
  agent: AgentNameSchema,
  incident_type: z.string().min(1),
  location: LocationSchema,
  severity: SeveritySchema,
  confidence: z.number().min(0).max(1),
  verification_status: VerificationStatusSchema,
  affected_route: z.boolean(),
  evidence: z.array(z.string()),
  source: z.array(z.string()),
  recommended_action: z.string().min(1),
  observed_at: z.string().datetime(),
  is_simulated: z.boolean(),
});

export type AgentContract = z.infer<typeof AgentContractSchema>;
export type Severity = z.infer<typeof SeveritySchema>;
export type VerificationStatus = z.infer<typeof VerificationStatusSchema>;
export type Location = z.infer<typeof LocationSchema>;
export type WaterIncidentType = z.infer<typeof WaterIncidentTypeSchema>;
