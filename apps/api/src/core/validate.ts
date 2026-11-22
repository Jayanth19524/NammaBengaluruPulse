import { z } from "zod";

export const AgentContractSchema = z.object({
  agent: z.enum(["FloodLens", "RoadTrust", "WaterWatch"]),
  incident_type: z.string().min(1),
  location: z.object({
    latitude: z.number().min(-90).max(90),
    longitude: z.number().min(-180).max(180),
  }),
  severity: z.enum(["info", "low", "moderate", "high", "critical"]),
  confidence: z.number().min(0).max(1),
  verification_status: z.enum(["confirmed", "reported", "predicted"]),
  affected_route: z.boolean(),
  evidence: z.array(z.string()),
  source: z.array(z.string()),
  recommended_action: z.string().min(1),
  observed_at: z.string(),
  is_simulated: z.boolean(),
});

export type AgentContract = z.infer<typeof AgentContractSchema>;

export function validateAgentContract(data: unknown): AgentContract {
  return AgentContractSchema.parse(data);
}

export function validateAgentContracts(data: unknown[]): AgentContract[] {
  return data.map(validateAgentContract);
}
