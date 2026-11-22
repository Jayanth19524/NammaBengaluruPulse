import { useMutation } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { runFlood } from "../api/client";
import type { FloodResult } from "../api/types";
import { BasisBadge, DemoTag, SeverityBadge } from "../design/Badges";
import { ago } from "../design/format";
import "./flood.css";

const hhmm = (iso?: string | null) => (iso ? new Date(iso).toLocaleString([], { weekday: "short", hour: "2-digit", minute: "2-digit", hour12: false }) : "");

function agentLine(a: FloodResult["agent"]) {
  if (a.mode === "llm") return `Investigated by an AI agent (${a.model}) calling the flood model as tools.`;
  if (a.mode === "deterministic_fallback") return "The AI agent did not finish, so the terrain-and-rainfall model ran on its own.";
  return "Terrain-and-rainfall model only: no AI model is configured.";
}

export default function FloodPanel({ onResult, onFocus }: {
  onResult: (r: FloodResult | null) => void; onFocus: (lat: number, lon: number) => void;
}) {
  const [scenario, setScenario] = useState(false);
  const m = useMutation({ mutationFn: () => runFlood(scenario), onSuccess: onResult });
  const started = useRef(false);
  useEffect(() => { if (!started.current) { started.current = true; m.mutate(); } }, []); // eslint-disable-line react-hooks/exhaustive-deps
  const r = m.data;
  const f = r?.forecast;
  return (
    <div>
      <div className="form">
        <strong>FloodLens</strong>
        <div className="muted">Predicts where flooding may happen along your routes from real elevation and rainfall forecasts.</div>
        <label className="check"><input type="checkbox" checked={scenario} onChange={(e) => setScenario(e.target.checked)} />
          What-if: heavy rain (a scenario, not a forecast)</label>
        <div><button className="btn primary" disabled={m.isPending} onClick={() => m.mutate()}>{m.isPending ? "Running…" : "Run FloodLens"}</button></div>
      </div>
      {m.error && <div className="state"><p className="err">FloodLens isn't reachable.</p><p className="faint">{String((m.error as Error).message)}</p></div>}
      {m.isPending && !r && <div><div className="skel" /><div className="skel" /></div>}
      {r && f && (
        <>
          <div className="flood-forecast" role="status">
            {!f.available ? <div className="err">Rainfall forecast unavailable, so risk can't be estimated.</div> : (
              <>
                <div className="faint">{f.is_scenario ? "What-if scenario (not a forecast)" : "Forecast, next " + (f.hours ?? 48) + " h"}</div>
                <div className="big">{f.accum_6h_mm} mm in 6 h · peak {f.peak_mm_h} mm/h</div>
                {!f.is_scenario && (f.peak_mm_h ?? 0) < 1 && <div className="muted">No significant rain forecast, so no flood risk is expected. The pale areas show low-lying ground that would collect water if heavy rain came.</div>}
                {f.window_start && <div className="muted">Heaviest rain {hhmm(f.window_start)} to {hhmm(f.window_end)}</div>}
              </>
            )}
            <div className="faint" style={{ marginTop: 4 }}>{agentLine(r.agent)} Checked {ago(r.audit.at)}.</div>
          </div>
          {r.agent.summary && <div className="note" style={{ margin: "0 16px 8px" }}>{r.agent.summary}</div>}
          <div className="group-title">Areas that may flood on your routes ({r.responses.length})</div>
          {r.responses.length === 0 && f.available && <div className="state">Nothing is expected to flood on your routes.</div>}
          {r.responses.map((x) => {
            const reasoning = x.evidence.find((e) => e.type === "agent_reasoning");
            return (
              <div key={x.incident_id} className="row" style={{ cursor: "default" }}>
                <div className="row-top"><span className="row-title">Possible flooding, {Math.round(x.distance_m)} m from {x.route_id}</span><SeverityBadge s={x.severity} /></div>
                <div className="row-sub"><BasisBadge b={x.verification_status} />{x.is_simulated && <DemoTag />}<span className="mono">risk {Math.round(x.risk * 100)}%</span></div>
                <div className="risk-bar"><i style={{ width: `${Math.round(x.risk * 100)}%` }} /></div>
                {reasoning && <p style={{ margin: "8px 0 0" }}>{String(reasoning.text)}</p>}
                <div className="action"><strong>What to do</strong><div>{x.recommended_action}</div></div>
                <button className="linkbtn" onClick={() => onFocus(x.location.latitude, x.location.longitude)}>View on map</button>
              </div>
            );
          })}
          <div className="note" style={{ margin: "8px 16px" }}>These are model estimates from terrain (about 90 m resolution) and rainfall. They are not validated against past floods and not measurements.</div>
          <details style={{ padding: "4px 16px 12px" }}>
            <summary style={{ cursor: "pointer", fontWeight: 500 }}>What the agent did ({r.trace.length} steps)</summary>
            <ol className="trace">{r.trace.map((t, i) => <li key={i}><span className="k">{t.kind}</span>{t.message}</li>)}</ol>
            <div className="faint" style={{ marginTop: 6 }}>Data sources: {r.source_health.map((h) => `${h.source} (${h.status})`).join(", ") || "none"}</div>
          </details>
        </>
      )}
    </div>
  );
}
