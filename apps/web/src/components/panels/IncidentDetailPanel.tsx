import React from "react";
import { Incident } from "../../types";
import { SeverityBadge } from "./SeverityBadge";
import { BasisBadge } from "./BasisBadge";
import { X, Droplets, MapPin, Clock, AlertCircle } from "lucide-react";

const INCIDENT_LABELS: Record<string, string> = {
  supply_disruption: "Supply disruption",
  tanker_shortage: "Tanker shortage",
  sensor_anomaly: "Sensor anomaly",
  demand_spike: "Demand spike",
};

interface Props {
  incident: Incident;
  onClose: () => void;
}

export function IncidentDetailPanel({ incident, onClose }: Props) {
  const title = INCIDENT_LABELS[incident.incident_type] ?? incident.incident_type;
  const time = new Date(incident.observed_at).toLocaleString("en-IN", {
    dateStyle: "medium",
    timeStyle: "short",
  });

  return (
    <div className="bg-white border border-border rounded-panel shadow-sm flex flex-col h-full">
      {/* Header */}
      <div className="flex items-start justify-between p-4 border-b border-border">
        <div className="flex items-center gap-2">
          <Droplets size={16} className="text-water shrink-0" strokeWidth={1.5} />
          <span className="text-sm font-semibold text-gray-900">{title}</span>
        </div>
        <button
          onClick={onClose}
          className="text-muted hover:text-gray-900 transition-colors p-0.5 rounded"
          aria-label="Close panel"
        >
          <X size={16} strokeWidth={1.5} />
        </button>
      </div>

      {/* Body */}
      <div className="p-4 flex flex-col gap-4 overflow-y-auto flex-1">
        {/* Badges */}
        <div className="flex items-center gap-2 flex-wrap">
          <SeverityBadge severity={incident.severity} />
          <BasisBadge
            verificationStatus={incident.verification_status}
            isSimulated={incident.is_simulated}
          />
        </div>

        {/* Location */}
        {incident.area_name && (
          <div className="flex items-start gap-2 text-sm text-gray-700">
            <MapPin size={14} className="text-muted mt-0.5 shrink-0" strokeWidth={1.5} />
            <span>{incident.area_name}</span>
          </div>
        )}

        {/* Observed at */}
        <div className="flex items-start gap-2 text-sm text-muted">
          <Clock size={14} className="mt-0.5 shrink-0" strokeWidth={1.5} />
          <span>{time}</span>
        </div>

        {/* Recommended action */}
        <div className="bg-surface border border-border rounded-control p-3">
          <p className="text-xs font-medium text-muted uppercase tracking-wide mb-1">
            Recommended action
          </p>
          <p className="text-sm text-gray-800">{incident.recommended_action}</p>
        </div>

        {/* Evidence */}
        {incident.evidence.length > 0 && (
          <div>
            <p className="text-xs font-medium text-muted uppercase tracking-wide mb-2">
              Evidence
            </p>
            <ul className="space-y-1">
              {incident.evidence.map((e, i) => (
                <li key={i} className="flex items-start gap-2 text-sm text-gray-700">
                  <AlertCircle
                    size={13}
                    className="text-muted mt-0.5 shrink-0"
                    strokeWidth={1.5}
                  />
                  {e}
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Sources */}
        {incident.source.length > 0 && (
          <div>
            <p className="text-xs font-medium text-muted uppercase tracking-wide mb-1">
              Source
            </p>
            <p className="text-sm text-gray-600">{incident.source.join(", ")}</p>
          </div>
        )}

        {/* Confidence */}
        <div className="text-xs text-muted">
          Confidence: {Math.round(incident.confidence * 100)}%
        </div>
      </div>
    </div>
  );
}
