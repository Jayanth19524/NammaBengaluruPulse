import { useRef, useEffect } from "react";
import type { AgentEvent, AgentEventKind, Health, InvestigateResult } from "../api/types";
import { DemoTag } from "../design/Badges";
import { useAgentLog } from "../api/useAgentLog";
import { ago } from "../design/format";

// ── icons (Lucide-style 1.5px stroke SVG, 14×14) ─────────────────────────────
const ICON: Record<AgentEventKind | "default", string> = {
  start:            "▶",
  adapter_fetch:    "↓",
  adapter_ok:       "✓",
  adapter_error:    "✗",
  dedup:            "⊕",
  geo_check:        "⊙",
  result:           "≡",
  done:             "●",
  report_submitted: "✎",
  default:          "·",
};

const KIND_COLOR: Record<AgentEventKind | "default", string> = {
  start:            "var(--accent)",
  adapter_fetch:    "var(--text-3)",
  adapter_ok:       "var(--sev-low)",
  adapter_error:    "var(--sev-critical)",
  dedup:            "var(--text-2)",
  geo_check:        "var(--accent)",
  result:           "var(--text)",
  done:             "var(--sev-low)",
  report_submitted: "var(--cat-road)",
  default:          "var(--text-3)",
};

function EventRow({ ev }: { ev: AgentEvent }) {
  const color = KIND_COLOR[ev.kind] ?? KIND_COLOR.default;
  const icon  = ICON[ev.kind]      ?? ICON.default;
  return (
    <div className="log-row">
      <span className="log-icon" style={{ color }}>{icon}</span>
      <span className="log-msg">{ev.message}</span>
      <span className="log-time faint">{ago(ev.at)}</span>
    </div>
  );
}

function RunningDot({ active }: { active: boolean }) {
  return (
    <span
      className={`running-dot${active ? " active" : ""}`}
      title={active ? "Agent is investigating…" : "Idle"}
    />
  );
}

export default function AgentStatus({ health, inv }: { health?: Health; inv?: InvestigateResult }) {
  const { events, connected } = useAgentLog();

  // Determine if an investigation is currently in-progress (started but not done)
  const lastStart = [...events].reverse().findIndex((e) => e.kind === "start");
  const lastDone  = [...events].reverse().findIndex((e) => e.kind === "done");
  const running   = lastStart !== -1 && (lastDone === -1 || lastStart < lastDone);

  // Auto-scroll the log to the bottom when new events arrive
  const logRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight;
    }
  }, [events.length]);

  return (
    <div className="detail">
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
        <h2 style={{ margin: 0 }}>RoadTrust</h2>
        <RunningDot active={running} />
        {running && <span className="faint" style={{ fontSize: 12 }}>Investigating…</span>}
      </div>
      <p className="muted">Watches road damage, closures and construction near your routes.</p>

      {/* Source health */}
      <dl className="kv">
        <dt>Photo analysis</dt>
        <dd>
          {health
            ? health.detector_available
              ? `Running (${health.detector})`
              : "Off — photos are stored but not analysed."
            : "Checking…"}
        </dd>
        <dt>Last check</dt>
        <dd>
          {inv
            ? `${inv.audit.routes} routes · ${inv.audit.active_incidents} active incidents · ${inv.audit.relevant} relevant`
            : "—"}
        </dd>
        <dt>SSE stream</dt>
        <dd style={{ color: connected ? "var(--sev-low)" : "var(--text-3)" }}>
          {connected ? "Live" : "Connecting…"}
        </dd>
      </dl>

      <strong>Data sources</strong>
      <ul className="evidence" style={{ marginBottom: 16 }}>
        {(inv?.source_health ?? []).map((s) => (
          <li key={s.source}>
            <div className="row-top">
              <span className="row-title">{s.source}</span>
              {s.simulated && <DemoTag />}
              <span className={s.status === "ok" ? "" : "err"}>
                {s.status === "ok" ? "OK" : "Unavailable"}
              </span>
            </div>
            {s.error && <div className="faint">{s.error}</div>}
          </li>
        ))}
        {!inv && <li className="faint">No data yet — investigation will run shortly.</li>}
      </ul>

      {/* Live execution log */}
      <strong>Execution log</strong>
      <div className="log-wrap" ref={logRef}>
        {events.length === 0 ? (
          <div className="faint log-empty">
            Waiting for the first investigation run…
          </div>
        ) : (
          [...events].reverse().map((ev, i) => <EventRow key={i} ev={ev} />)
        )}
      </div>

      {inv?.source_health.some((s) => s.simulated) && (
        <div className="note" style={{ marginTop: 8 }}>
          Some incidents come from a demo feed and are labelled as demo data.
        </div>
      )}
    </div>
  );
}
