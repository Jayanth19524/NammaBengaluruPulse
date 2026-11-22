/**
 * useAgentLog — subscribes to the RoadTrust /log SSE stream and returns a live
 * list of agent execution events. Falls back to a snapshot poll if SSE is unavailable.
 */
import { useEffect, useRef, useState } from "react";
import type { AgentEvent } from "../api/types";

export function useAgentLog(): { events: AgentEvent[]; connected: boolean } {
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const esRef = useRef<EventSource | null>(null);

  useEffect(() => {
    // Load snapshot first so the view isn't blank on mount
    fetch("/api/log/snapshot")
      .then((r) => r.json())
      .then((d) => setEvents(d.events ?? []))
      .catch(() => undefined);

    const es = new EventSource("/api/log");
    esRef.current = es;

    es.onopen = () => setConnected(true);
    es.onerror = () => setConnected(false);
    es.onmessage = (e) => {
      try {
        const ev: AgentEvent = JSON.parse(e.data);
        setEvents((prev) => {
          // Avoid duplicates if the snapshot overlapped
          const last = prev[prev.length - 1];
          if (last && last.at === ev.at && last.kind === ev.kind) return prev;
          return [...prev.slice(-199), ev]; // keep last 200
        });
      } catch {
        // keepalive ping or malformed — ignore
      }
    };

    return () => {
      es.close();
      esRef.current = null;
      setConnected(false);
    };
  }, []);

  return { events, connected };
}
