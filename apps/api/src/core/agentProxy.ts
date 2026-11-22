import dotenv from "dotenv";
dotenv.config();
import { log } from "./logger";

const PYTHON_AGENT_URL = process.env.PYTHON_AGENT_URL ?? "http://localhost:8000";
const TIMEOUT_MS = 10000;
const MAX_RETRIES = 2;

export interface ScanRequest {
  latitude: number;
  longitude: number;
  radius_m: number;
}

export interface AgentScanResponse {
  incidents: unknown[];
  adapter: string;
  scan_lat: number;
  scan_lng: number;
  radius_m: number;
}

async function sleep(ms: number): Promise<void> {
  return new Promise((r) => setTimeout(r, ms));
}

export async function callWaterWatchAgent(req: ScanRequest): Promise<AgentScanResponse> {
  let lastError: Error | null = null;

  for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
    if (attempt > 0) await sleep(500 * attempt);

    try {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);

      const res = await fetch(`${PYTHON_AGENT_URL}/agent/waterwatch/scan`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(req),
        signal: controller.signal,
      });
      clearTimeout(timer);

      if (!res.ok) {
        throw new Error(`Agent returned HTTP ${res.status}`);
      }

      return (await res.json()) as AgentScanResponse;
    } catch (err: unknown) {
      lastError = err instanceof Error ? err : new Error(String(err));
      log("warn", `[agentProxy] attempt ${attempt + 1} failed: ${lastError.message}`);
    }
  }

  throw new Error(`WaterWatch agent unavailable after ${MAX_RETRIES + 1} attempts: ${lastError?.message}`);
}
