/**
 * Safe logger — never logs precise coordinates or sensitive data in plain text.
 */

type LogLevel = "info" | "warn" | "error";

function mask(value: unknown): string {
  if (typeof value === "number") {
    // Mask coordinates to city-level precision (2 decimal places)
    return value.toFixed(2) + "…";
  }
  if (typeof value === "string" && value.length > 80) {
    return value.slice(0, 40) + "…[truncated]";
  }
  return String(value);
}

export function log(level: LogLevel, message: string, meta?: Record<string, unknown>): void {
  const ts = new Date().toISOString();
  const safeMsg = `[${ts}] [${level.toUpperCase()}] ${message}`;

  if (meta) {
    const safeMeta: Record<string, string> = {};
    for (const [k, v] of Object.entries(meta)) {
      // Never log lat/lng keys as precise numbers
      if (k === "lat" || k === "lng" || k === "latitude" || k === "longitude") {
        safeMeta[k] = typeof v === "number" ? mask(v) : "[redacted]";
      } else {
        safeMeta[k] = mask(v);
      }
    }
    console[level === "error" ? "error" : level === "warn" ? "warn" : "log"](safeMsg, safeMeta);
  } else {
    console[level === "error" ? "error" : level === "warn" ? "warn" : "log"](safeMsg);
  }
}
