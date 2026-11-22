import React from "react";
import { Notification } from "../../types";
import { SeverityBadge } from "./SeverityBadge";
import { Bell, X } from "lucide-react";

interface Props {
  notifications: Notification[];
  onDismiss?: (id: string) => void;
}

export function AlertPanel({ notifications, onDismiss }: Props) {
  if (notifications.length === 0) {
    return (
      <div className="bg-white border border-border rounded-panel p-4">
        <p className="text-sm text-muted">No water alerts for this area.</p>
      </div>
    );
  }

  return (
    <div className="bg-white border border-border rounded-panel overflow-hidden">
      <div className="flex items-center justify-between px-4 py-3 border-b border-border">
        <div className="flex items-center gap-2">
          <Bell size={14} strokeWidth={1.5} className="text-muted" />
          <span className="text-xs font-semibold text-gray-700 uppercase tracking-wide">
            Alerts
          </span>
        </div>
        <span className="text-xs text-muted">{notifications.length} active</span>
      </div>
      <ul className="divide-y divide-border max-h-72 overflow-y-auto">
        {notifications.map((n) => (
          <li
            key={n.id}
            className={`px-4 py-3 flex items-start gap-3 ${
              n.is_read ? "opacity-60" : ""
            }`}
          >
            <div className="mt-0.5">
              <SeverityBadge severity={n.severity} />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm text-gray-800 leading-snug">{n.alert_copy}</p>
              <p className="text-xs text-muted mt-1">
                {new Date(n.created_at).toLocaleString("en-IN", {
                  timeStyle: "short",
                  dateStyle: "short",
                })}
              </p>
            </div>
            {onDismiss && (
              <button
                onClick={() => onDismiss(n.id)}
                className="text-muted hover:text-gray-900 shrink-0 p-0.5"
                aria-label="Dismiss"
              >
                <X size={13} strokeWidth={1.5} />
              </button>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
