import React, { useState, useEffect } from "react";
import { WaterMap } from "./components/map/WaterMap";
import { AlertPanel } from "./components/panels/AlertPanel";
import { NotificationToast } from "./components/panels/NotificationToast";
import { StatusLine } from "./components/StatusLine";
import { useNotifications } from "./hooks/useNotifications";
import { Notification } from "./types";
import { Droplets } from "lucide-react";

export default function App() {
  const { data: notifications = [], dataUpdatedAt } = useNotifications();
  const [dismissedIds, setDismissedIds] = useState<Set<string>>(new Set());
  const [toastNotif, setToastNotif] = useState<Notification | null>(null);
  const prevCountRef = React.useRef(0);

  // Show toast when new notifications arrive
  useEffect(() => {
    const unread = notifications.filter((n) => !n.is_read && !dismissedIds.has(n.id));
    if (unread.length > prevCountRef.current && unread.length > 0) {
      setToastNotif(unread[0]);
    }
    prevCountRef.current = unread.length;
  }, [notifications, dismissedIds]);

  const lastCheckMins = dataUpdatedAt
    ? Math.floor((Date.now() - dataUpdatedAt) / 60000)
    : 0;

  const visibleNotifs = notifications.filter((n) => !dismissedIds.has(n.id));

  function dismiss(id: string) {
    setDismissedIds((prev) => new Set([...prev, id]));
    if (toastNotif?.id === id) setToastNotif(null);
  }

  return (
    <div className="flex flex-col h-screen bg-surface font-sans text-gray-900">
      {/* Top bar */}
      <header className="flex items-center justify-between px-4 py-2.5 bg-white border-b border-border shrink-0">
        <div className="flex items-center gap-2">
          <Droplets size={18} className="text-water" strokeWidth={1.5} />
          <span className="text-sm font-semibold tracking-tight">WaterWatch</span>
          <span className="text-xs text-muted ml-1">· NammaPulse</span>
        </div>
        <StatusLine lastCheckMins={lastCheckMins} />
      </header>

      {/* Main content */}
      <div className="flex flex-1 overflow-hidden">
        {/* Map takes full area */}
        <main className="flex-1 relative overflow-hidden">
          <WaterMap />
        </main>

        {/* Right sidebar: alert panel — desktop only */}
        <aside className="hidden lg:flex flex-col w-72 border-l border-border bg-white overflow-y-auto">
          <div className="p-4 border-b border-border shrink-0">
            <h2 className="text-xs font-semibold text-muted uppercase tracking-wide">
              Active alerts
            </h2>
          </div>
          <div className="p-4 flex-1">
            <AlertPanel notifications={visibleNotifs} onDismiss={dismiss} />
          </div>
        </aside>
      </div>

      {/* Toast notification */}
      {toastNotif && (
        <div className="fixed bottom-4 right-4 z-[2000]">
          <NotificationToast
            notification={toastNotif}
            onDismiss={() => dismiss(toastNotif.id)}
          />
        </div>
      )}
    </div>
  );
}
