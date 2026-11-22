import { useMutation } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { planTrip } from "../api/client";
import type { DepartureOption, PlannedRoute, TripPlan } from "../api/types";
import { BasisBadge, DemoTag, KIND_LABEL, SeverityBadge } from "../design/Badges";

export interface Pt { lat: number; lon: number }
export type Stage = "origin" | "dest" | null;

const mins = (s: number) => `${Math.round(s / 60)} min`;
const clock = (iso: string) => new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", hour12: false });
const km = (m: number) => `${(m / 1000).toFixed(1)} km`;

function localInputNow(): string {
  const d = new Date(Date.now() - new Date().getTimezoneOffset() * 60000);
  return d.toISOString().slice(0, 16);
}

function RouteCard({ r, selected, onSelect }: { r: PlannedRoute; selected: boolean; onSelect: () => void }) {
  const p = r.prediction;
  const gap = p.predicted_s - p.snapshot_s;
  return (
    <button className="row" aria-current={selected} onClick={onSelect}>
      <div className="row-top">
        <span className="row-title">{r.via.length ? `via ${r.via.join(", ")}` : "Route"}</span>
        {r.recommended && <span className="basis" data-b="confirmed">Recommended</span>}
      </div>
      <div className="eta"><span className="eta-n">{mins(p.predicted_s)}</span>
        <span className="muted"> expected · {km(r.distance_m)} · arrive {clock(p.arrive_at)}</span></div>
      <div className="row-sub">
        <span className="mono">range {mins(p.low_s)}–{mins(p.high_s)}</span>
        {r.delta_vs_best_s >= 60 && <span>+{mins(r.delta_vs_best_s)} vs fastest</span>}
      </div>
      {gap >= 120 && (
        <div className="note">A time at departure would show {mins(p.snapshot_s)}. Traffic builds along the way, so expect about {mins(gap)} more.</div>
      )}
      {r.warnings.map((w, i) => (
        <div key={i} className="row-sub" style={{ marginTop: 6 }}>
          <span>{KIND_LABEL[w.kind]} ahead</span><SeverityBadge s={w.severity} /><BasisBadge b={w.basis} />{w.simulated && <DemoTag />}
        </div>
      ))}
    </button>
  );
}

function Departures({ opts }: { opts: DepartureOption[] }) {
  if (opts.length < 2) return null;
  const best = Math.min(...opts.map((o) => o.predicted_s));
  const spread = Math.max(...opts.map((o) => o.predicted_s)) - best;
  const flat = spread < 120; // too similar to call one "shortest"
  return (
    <div style={{ padding: "12px 16px" }}>
      <strong>When to leave</strong>
      <table className="dep"><tbody>
        {opts.map((o) => (
          <tr key={o.depart_at} className={!flat && o.predicted_s === best ? "best" : ""}>
            <td className="mono">{clock(o.depart_at)}</td><td>{mins(o.predicted_s)}</td>
            <td className="faint">arrive {clock(o.arrive_at)}{!flat && o.predicted_s === best ? " · shortest" : ""}</td>
          </tr>
        ))}
      </tbody></table>
      <div className="faint" style={{ marginTop: 4 }}>{flat ? "Little difference across these times. " : ""}For the recommended route.</div>
    </div>
  );
}

export default function TripPanel({ origin, dest, stage, setStage, onClear, onPlan, selectedRoute, setSelectedRoute }: {
  origin: Pt | null; dest: Pt | null; stage: Stage; setStage: (s: Stage) => void; onClear: () => void;
  onPlan: (p: TripPlan | null) => void; selectedRoute: string | null; setSelectedRoute: (id: string) => void;
}) {
  const [when, setWhen] = useState(localInputNow());
  const [now, setNow] = useState(true);
  const m = useMutation({ mutationFn: () => planTrip(origin!, dest!, now ? null : when), onSuccess: (p) => { onPlan(p); setSelectedRoute(p.routes[0].id); } });
  useEffect(() => { m.reset(); onPlan(null); }, [origin, dest]); // eslint-disable-line react-hooks/exhaustive-deps
  const plan = m.data;
  const fmt = (p: Pt | null) => p ? `${p.lat.toFixed(4)}, ${p.lon.toFixed(4)}` : "Not set";
  return (
    <div>
      <div className="form">
        <strong>Plan a trip</strong>
        <div className="loc">
          <div className="row-top"><span className="muted">Start</span><span className="mono" style={{ flex: 1 }}>{fmt(origin)}</span>
            <button className="linkbtn" onClick={() => setStage("origin")}>{stage === "origin" ? "Click the map…" : origin ? "Change" : "Set on map"}</button></div>
          <div className="row-top" style={{ marginTop: 6 }}><span className="muted">End</span><span className="mono" style={{ flex: 1 }}>{fmt(dest)}</span>
            <button className="linkbtn" onClick={() => setStage("dest")}>{stage === "dest" ? "Click the map…" : dest ? "Change" : "Set on map"}</button></div>
        </div>
        <div className="field"><label>Leave</label>
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <label className="check"><input type="radio" checked={now} onChange={() => setNow(true)} /> Now</label>
            <label className="check"><input type="radio" checked={!now} onChange={() => setNow(false)} /> At</label>
            <input type="datetime-local" className="input" style={{ flex: 1 }} disabled={now} value={when} onChange={(e) => setWhen(e.target.value)} />
          </div></div>
        {m.error && <div className="err">{(m.error as Error).message}</div>}
        <div style={{ display: "flex", gap: 8 }}>
          <button className="btn primary" disabled={!origin || !dest || m.isPending} onClick={() => m.mutate()}>{m.isPending ? "Finding routes…" : "Find routes"}</button>
          <button className="btn" onClick={() => { onClear(); m.reset(); }}>Clear</button>
        </div>
      </div>
      {m.isPending && <div><div className="skel" /><div className="skel" /></div>}
      {plan && (
        <>
          <div className="group-title">{plan.routes.length === 1 ? "Route" : `Routes (${plan.routes.length})`}</div>
          {plan.routes.map((r) => <RouteCard key={r.id} r={r} selected={r.id === selectedRoute} onSelect={() => setSelectedRoute(r.id)} />)}
          {plan.routes.length === 1 && <div className="state faint">No meaningfully different alternative road was found for this trip.</div>}
          <Departures opts={plan.departure_options} />
          <div className="note" style={{ margin: "0 16px 16px" }}>
            {plan.live_traffic ? `Adjusted with live traffic from ${plan.live_traffic}.` : "Estimated from an assumed time-of-day traffic pattern, not live traffic. Treat it as a guide."}
            {" "}Road incidents: {plan.road_incidents}.
          </div>
        </>
      )}
    </div>
  );
}
