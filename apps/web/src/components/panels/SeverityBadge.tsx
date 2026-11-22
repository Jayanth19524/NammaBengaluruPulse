import React from "react";

type Severity = "info" | "low" | "moderate" | "high" | "critical";

const SEVERITY_STYLES: Record<Severity, { dot: string; label: string; text: string }> = {
  info:     { dot: "bg-gray-400",   label: "Info",     text: "text-gray-600" },
  low:      { dot: "bg-green-600",  label: "Low",      text: "text-green-700" },
  moderate: { dot: "bg-yellow-500", label: "Moderate", text: "text-yellow-700" },
  high:     { dot: "bg-orange-500", label: "High",     text: "text-orange-700" },
  critical: { dot: "bg-red-600",    label: "Critical", text: "text-red-700" },
};

export function SeverityBadge({ severity }: { severity: string }) {
  const s = (severity ?? "info") as Severity;
  const style = SEVERITY_STYLES[s] ?? SEVERITY_STYLES.info;
  return (
    <span className={`inline-flex items-center gap-1 text-xs font-medium ${style.text}`}>
      <span className={`inline-block w-2 h-2 rounded-full ${style.dot}`} />
      {style.label}
    </span>
  );
}
