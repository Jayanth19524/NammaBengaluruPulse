import { useMutation } from "@tanstack/react-query";
import { useEffect, useRef } from "react";
import { runCheck } from "../api/client";
import type { Decision, MonitoredRoute, Run } from "../api/types";
import { BasisBadge, SeverityBadge } from "../design/Badges";
import { ago } from "../design/format";
import { DEMO_COMMUTE } from "../demo";

const PART_LABEL: Record<string, string> = { severity: "Severity", proximity: "Closeness to route", basis: "Source reliability", confidence: "Confidence" };

function AlertCard({ d, onOpen }: { d: Decision; onOpen?: () => void }) {
  const f = d.finding;
  return (
    <div className="row" style={{ cursor: "default" }}>
      <div className="row-top">
        <span className="row-title">{f.title}</span><SeverityBadge s={f.severity} />
      </div>
      <div className="row-sub"><BasisBadge b={f.basis} /><span className="mono">relevance {f.score.toFixed(2)}</span></div>
      {f.explanation && <p style={{ margin: "8px 0 0" }}>{f.explanation}</p>}
      <div className="action"><strong>What to do</strong><div>{f.action}</div></div>
      <details>
        <summary className="muted" style={{ cursor: "pointer" }}>Why am I seeing this?</summary>
        <ul className="evidence">{d.reasons.map((r, i) => <li key={i}>{r}</li>)}
          <li className="mono">{Object.entries(f.score_parts).map(([k, v]) => `${PART_LABEL[k] ?? k} ${v}`).join(" · ")}</li></ul>
      </details>
      {onOpen && <button className="linkbtn" style={{ marginTop: 6 }} onClick={onOpen}>View on map</button>}
    </div>
  );
}

export default function AlertsPanel({ routes, onRemove, onOpenIncident }: {
  routes: MonitoredRoute[]; onRemove: (id: string) => void; onOpenIncident: (id: string) => void;
}) {
  const watched = routes.length ? routes : [DEMO_COMMUTE];
  const m = useMutation({ mutationFn: () => runCheck(watched) });
  const started = useRef(false);
  useEffect(() => { if (!started.current) { started.current = true; m.mutate(); } }, []); // eslint-disable-line react-hooks/exhaustive-deps
  const run: Run | undefined = m.data;
  const alerts = run?.decisions.filter((d) => d.action === "alert") ?? [];
  const quiet = run?.decisions.filter((d) => d.action === "suppress") ?? [];
  return (
    <div>
      <div className="form">
        <strong>Watching</strong>
        {watched.map((r) => (
          <div key={r.id} className="row-top">
            <span className="row-title">{r.name}{r.demo ? " (demo)" : ""}</span>
            {!r.demo && <button className="linkbtn" onClick={() => onRemove(r.id)}>Remove</button>}
          </div>
        ))}
        {!routes.length && <div className="faint">Save a trip from the Trip tab to watch your own route.</div>}
        <div><button className="btn primary" disabled={m.isPending} onClick={() => m.mutate()}>{m.isPending ? "Checking…" : "Run check now"}</button></div>
      </div>
      {m.error && <div className="state"><p className="err">The orchestrator isn't reachable.</p><p className="faint">{String((m.error as Error).message)}</p></div>}
      {m.isPending && !run && <div><div className="skel" /><div className="skel" /></div>}
      {run && (
        <>
          <div className="note" style={{ margin: "0 16px 8px" }} role="status">
            {run.summary.headline}. Checked {ago(run.at)}.
            <div className="faint">{run.summary.mode === "llm" ? `Investigated by an AI agent (${run.summary.model}).`
              : run.summary.mode === "deterministic_fallback" ? "The AI agent did not finish, so fixed checks were used."
              : "Fixed checks only: no AI model is configured."}</div>
          </div>
          {alerts.length > 0 && <div className="group-title">Alerts ({alerts.length})</div>}
          {alerts.map((d) => <AlertCard key={d.key} d={d} onOpen={d.finding.incident_id ? () => onOpenIncident(d.finding.incident_id!) : undefined} />)}
          {quiet.length > 0 && <div className="group-title">Checked, not alerted ({quiet.length})</div>}
          {quiet.map((d) => (
            <div key={d.key} className="row" style={{ cursor: "default" }}>
              <div className="row-top"><span className="row-title">{d.finding.title}</span><SeverityBadge s={d.finding.severity} /></div>
              <div className="row-sub">{d.reasons[0]}</div>
            </div>
          ))}
          <details style={{ padding: "12px 16px" }}>
            <summary style={{ cursor: "pointer", fontWeight: 500 }}>Decision log ({run.events.length} steps)</summary>
            <ol className="evidence" style={{ paddingLeft: 0 }}>
              {run.events.map((e, i) => (
                <li key={i}><span className="mono faint">{e.node}</span>{" "}
                  <span className={e.level === "warn" ? "err" : ""}>{e.message}</span></li>
              ))}
            </ol>
          </details>
        </>
      )}
    </div>
  );
}
