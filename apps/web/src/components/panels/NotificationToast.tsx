import React from "react";
import { Notification } from "../../types";

interface Props {
  notification: Notification;
  onDismiss: () => void;
}

const SEVERITY_BORDER: Record<string, string> = {
  critical: "border-l-red-600",
  high: "border-l-orange-500",
  moderate: "border-l-yellow-500",
  low: "border-l-green-600",
  info: "border-l-gray-400",
};

export function NotificationToast({ notification, onDismiss }: Props) {
  const borderColor = SEVERITY_BORDER[notification.severity] ?? "border-l-gray-400";
  return (
    <div
      role="alert"
      className={`bg-white border border-border border-l-4 ${borderColor} rounded-panel shadow-sm px-4 py-3 max-w-sm w-full`}
    >
      <div className="flex items-start justify-between gap-3">
        <p className="text-sm text-gray-800 leading-snug flex-1">
          {notification.alert_copy}
        </p>
        <button
          onClick={onDismiss}
          className="text-muted hover:text-gray-900 shrink-0 p-0.5"
          aria-label="Dismiss notification"
        >
          ×
        </button>
      </div>
    </div>
  );
}
