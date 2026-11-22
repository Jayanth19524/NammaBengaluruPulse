import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import type { FloodResult } from "../api/types";
import "./architecture.css";

type Svc = { name: string; url: string; ok: boolean; detail: string };
const SERVICES = [
  { name: "FloodLens", url: "/flood/health" }, { name: "RoadTrust", url: "/api/health" },
  { name: "TripCast", url: "/trip/health" }, { name: "Orchestrator", url: "/orch/health" },
];

/** Live status: each service's own /health, polled. A failed request means the service is down. */
export function useServices() {
  return useQuery({
    queryKey: ["arch-health"], refetchInterval: 8000,
    queryFn: async (): Promise<Record<string, Svc & { raw?: Record<string, unknown> }>> => {
      const out: Record<string, Svc & { raw?: Record<string, unknown> }> = {};
      await Promise.all(SERVICES.map(async (s) => {
        try {
          const r = await fetch(s.url, { signal: AbortSignal.timeout(4000) });
          if (!r.ok) throw new Error(String(r.status));
          const raw = await r.json();
          const mode = raw.agent_mode ?? raw.mode;
          out[s.name] = { ...s, ok: true, raw, detail: mode === "llm" ? `AI agent (${raw.model})` : mode ? "no AI model configured" : "running" };
        } catch { out[s.name] = { ...s, ok: false, detail: "not reachable" }; }
      }));
      return out;
    },
  });
}

// ---- diagram geometry (1200 x 640 viewBox) ---------------------------------------------------------------------
interface N { id: string; x: number; y: number; w: number; h: number; title: string; tag?: string }
const W = 210, H = 66;
const NODES: N[] = [
  { id: "routes", x: 24, y: 70, w: W, h: H, title: "Monitored routes", tag: "INPUT" },
  { id: "forecast", x: 24, y: 160, w: W, h: H, title: "Rainfall forecast", tag: "INPUT · OPEN-METEO" },
  { id: "elevation", x: 24, y: 250, w: W, h: H, title: "Terrain elevation", tag: "INPUT · OPEN-METEO DEM" },
  { id: "reports", x: 24, y: 340, w: W, h: H, title: "Community reports", tag: "INPUT" },
  { id: "model", x: 330, y: 160, w: W, h: H, title: "Flood-risk model", tag: "FLOODLENS · DETERMINISTIC" },
  { id: "grid", x: 330, y: 250, w: W, h: H, title: "Terrain grid & relief", tag: "FLOODLENS" },
  { id: "cluster", x: 330, y: 340, w: W, h: H, title: "Areas touching routes", tag: "FLOODLENS" },
  { id: "agent", x: 630, y: 70, w: 230, h: H, title: "Language-model agent", tag: "FLOODLENS · LLM + TOOLS" },
  { id: "guard", x: 630, y: 340, w: 230, h: H, title: "Completeness guard", tag: "FLOODLENS · POLICY" },
  { id: "map", x: 930, y: 160, w: 246, h: H, title: "3D flood map", tag: "OUTPUT" },
  { id: "findings", x: 930, y: 340, w: 246, h: H, title: "Findings & advice", tag: "OUTPUT" },
  { id: "orch", x: 930, y: 450, w: 246, h: H, title: "Orchestrator", tag: "LANGGRAPH · ALERT POLICY" },
  { id: "roadtrust", x: 630, y: 450, w: 230, h: 56, title: "RoadTrust", tag: "OTHER AGENT" },
  { id: "tripcast", x: 630, y: 520, w: 230, h: 56, title: "TripCast", tag: "OTHER AGENT" },
];
const EDGES: [string, string][] = [
  ["elevation", "grid"], ["forecast", "model"], ["reports", "model"], ["grid", "model"], ["model", "cluster"],
  ["routes", "cluster"], ["agent", "model"], ["cluster", "guard"], ["agent", "guard"], ["model", "map"],
  ["guard", "findings"], ["findings", "orch"], ["roadtrust", "orch"], ["tripcast", "orch"],
];
const byId = Object.fromEntries(NODES.map((n) => [n.id, n]));
const svcOf: Record<string, string> = { model: "FloodLens", grid: "FloodLens", cluster: "FloodLens", guard: "FloodLens", agent: "FloodLens",
  roadtrust: "RoadTrust", tripcast: "TripCast", orch: "Orchestrator" };

function path(a: N, b: N): string {
  if (a.x === b.x) {  // same column: bottom of the upper to top of the lower
    const [up, dn] = a.y < b.y ? [a, b] : [b, a];
    const x = up.x + up.w / 2;
    return `M${x},${up.y + up.h} L${x},${dn.y}`;
  }
  const [s, t] = a.x < b.x ? [a, b] : [b, a];
  const sx = s.x + s.w, sy = s.y + s.h / 2, tx = t.x, ty = t.y + t.h / 2, mx = (sx + tx) / 2;
  return `M${sx},${sy} C${mx},${sy} ${mx},${ty} ${tx},${ty}`;
}

// ---- turn the real trace into steps ---------------------------------------------------------------------------
interface Step { nodes: string[]; edges: [string, string][]; msg: string; kind: string; at: string; bad?: boolean }
function toStep(t: FloodResult["trace"][number]): Step {
  const base = { msg: t.message, kind: t.kind, at: t.at };
  const m = t.message.toLowerCase();
  if (t.kind === "fetch" && m.includes("rainfall")) return { ...base, nodes: ["forecast", "model"], edges: [["forecast", "model"]] };
  if (t.kind === "fetch") return { ...base, nodes: ["elevation", "grid"], edges: [["elevation", "grid"]] };
  if (t.kind === "scenario" || t.kind === "forecast") return { ...base, nodes: ["forecast", "model"], edges: [["forecast", "model"]] };
  if (t.kind === "terrain") return { ...base, nodes: ["grid", "model", "reports"], edges: [["grid", "model"], ["reports", "model"]] };
  if (t.kind === "assess") return { ...base, nodes: ["model", "cluster", "routes"], edges: [["model", "cluster"], ["routes", "cluster"]] };
  if (t.kind === "done") return { ...base, nodes: ["cluster", "guard", "findings", "map", "model"], edges: [["cluster", "guard"], ["guard", "findings"], ["model", "map"]] };
  if (t.kind === "agent_tool_call") return { ...base, nodes: ["agent", "model"], edges: [["agent", "model"]] };
  if (t.kind === "agent_tool_result") return { ...base, nodes: ["agent", "model"], edges: [["agent", "model"]] };
  if (t.kind === "agent_reasoning") return { ...base, nodes: ["agent"], edges: [] };
  if (t.kind === "agent_final") return { ...base, nodes: ["agent", "guard"], edges: [["agent", "guard"]] };
  if (t.kind === "agent_policy") return { ...base, nodes: ["guard", "cluster"], edges: [["cluster", "guard"]] };
  if (t.kind.includes("error")) return { ...base, nodes: m.includes("elevation") ? ["elevation"] : m.includes("forecast") ? ["forecast"] : ["agent"], edges: [], bad: true };
  return { ...base, nodes: [], edges: [] };
}

export function ArchitectureView({ result, onRun, running }: { result: FloodResult | null; onRun: () => void; running: boolean }) {
  const svc = useServices().data;
  const steps = useMemo(() => (result?.trace ?? []).map(toStep), [result]);
  const [i, setI] = useState(0);
  const [playing, setPlaying] = useState(false);
  useEffect(() => { setI(0); setPlaying(steps.length > 0); }, [steps.length, result?.audit.at]);
  useEffect(() => {
    if (!playing || steps.length === 0) return;
    const id = setInterval(() => setI((x) => { if (x >= steps.length - 1) { setPlaying(false); return x; } return x + 1; }), 1300);
    return () => clearInterval(id);
  }, [playing, steps.length]);

  const cur = steps[i];
  const used = new Set(steps.flatMap((s) => s.nodes));
  const t0 = steps[0] ? new Date(steps[0].at).getTime() : 0;
  const sub = (id: string): string => {
    if (!result) return "";
    const f = result.forecast;
    switch (id) {
      case "routes": return `${result.audit.routes} route(s)`;
      case "forecast": return f.available ? (f.is_scenario ? "what-if scenario, not a forecast" : `${f.accum_6h_mm} mm in 6 h · peak ${f.peak_mm_h} mm/h`) : "unavailable";
      case "elevation": return `${result.audit.cells} grid cells read`;
      case "reports": return svc?.FloodLens?.raw ? `${svc.FloodLens.raw.active_reports ?? 0} active` : "";
      case "model": return `${result.risk_map.features.filter((c) => Number(c.properties?.risk) >= 0.25).length} cells above alert level`;
      case "grid": return `${result.risk_map.features.filter((c) => Number(c.properties?.relief_m) >= 3).length} low-lying cells`;
      case "cluster": return `${result.responses.length} area(s) on your routes`;
      case "agent": return result.agent.mode === "llm" ? `${result.agent.model} · ${result.agent.steps} steps` : result.agent.mode === "deterministic_fallback" ? "did not finish; model ran alone" : "not used: no AI model configured";
      case "guard": return "reports every at-risk area, even if the model skips it";
      case "map": return `${result.risk_map.features.length} cells drawn`;
      case "findings": return `${result.responses.length} finding(s)`;
      default: return svc?.[({ roadtrust: "RoadTrust", tripcast: "TripCast", orch: "Orchestrator" } as Record<string, string>)[id]]?.detail ?? "";
    }
  };
  const nodeOn = (id: string) => !!cur && cur.nodes.includes(id);
  const nodeDim = (id: string) => !!result && !used.has(id) && !["map", "findings", "orch", "roadtrust", "tripcast"].includes(id);

  return (
    <div className="arch">
      <div className="arch-bar">
        <strong>Live architecture</strong>
        <span className="muted">Replay of FloodLens's last real run. Every step and number comes from that run's own trace.</span>
        <span className="grow" />
        <button className="btn" disabled={steps.length === 0} onClick={() => { if (i >= steps.length - 1) setI(0); setPlaying((p) => !p); }}>{playing ? "Pause" : "Play"}</button>
        <button className="btn" disabled={steps.length === 0 || i >= steps.length - 1} onClick={() => { setPlaying(false); setI((x) => Math.min(steps.length - 1, x + 1)); }}>Next step</button>
        <button className="btn primary" disabled={running} onClick={onRun}>{running ? "Running…" : "Run FloodLens now"}</button>
      </div>
      <svg className="arch-svg" viewBox="0 0 1200 620" preserveAspectRatio="xMidYMid meet" role="img"
           aria-label="Architecture diagram: inputs, FloodLens engine and agent, outputs, and the orchestrator">
        <text className="arch-col" x="24" y="40">Data in</text>
        <text className="arch-col" x="330" y="40">FloodLens engine</text>
        <text className="arch-col" x="630" y="40">Agent and guard</text>
        <text className="arch-col" x="930" y="40">Output</text>
        {EDGES.map(([a, b]) => {
          const on = !!cur && cur.edges.some(([x, y]) => (x === a && y === b) || (x === b && y === a));
          return <path key={a + b} className={`arch-edge${on ? " on" : ""}`} d={path(byId[a], byId[b])} />;
        })}
        {NODES.map((n) => {
          const s = svcOf[n.id] ? svc?.[svcOf[n.id]] : undefined;
          const bad = (nodeOn(n.id) && cur?.bad) || (s && !s.ok);
          return (
            <g key={n.id} className={`arch-node${nodeOn(n.id) ? " on" : ""}${bad ? " bad" : ""}${nodeDim(n.id) ? " dim" : ""}`} transform={`translate(${n.x},${n.y})`}>
              <rect width={n.w} height={n.h} rx="8" />
              <text className="tag" x="12" y="17">{n.tag}</text>
              <text className="tt" x="12" y="37">{n.title}</text>
              <text className="ss" x="12" y="55">{(sub(n.id) || (s && !s.ok ? "not reachable" : "")).slice(0, 38)}</text>
              {s && <circle cx={n.w - 14} cy={14} r="4" fill={s.ok ? "var(--sev-low)" : "var(--sev-critical)"} />}
            </g>
          );
        })}
      </svg>
      <div className="arch-cap" role="status" aria-live="polite">
        {!result ? <span className="muted">No FloodLens run yet. Run it to record a trace and replay it here.</span> : !cur ? <span className="muted">This run recorded no steps.</span> : (
          <>
            <div className="t">step {i + 1} of {steps.length} · {cur.kind} · +{((new Date(cur.at).getTime() - t0) / 1000).toFixed(1)} s</div>
            <div>{cur.msg}</div>
          </>
        )}
      </div>
    </div>
  );
}

export function ArchitecturePanel({ result, step, onStep }: { result: FloodResult | null; step: number; onStep: (i: number) => void }) {
  const svc = useServices();
  return (
    <div>
      <div className="group-title">Services now</div>
      {SERVICES.map((s) => {
        const v = svc.data?.[s.name];
        return <div key={s.name} className="svc"><span className={`dot ${v && !v.ok ? "down" : ""}`} /><span className="row-title">{s.name}</span>
          <span className="muted">{v ? v.detail : "checking…"}</span></div>;
      })}
      <div className="note" style={{ margin: "12px 16px" }}>Status refreshes every 8 seconds from each service's own health check.</div>
      <div className="group-title">Steps in the last FloodLens run ({result?.trace.length ?? 0})</div>
      <ol className="steps">
        {(result?.trace ?? []).map((t, k) => <li key={k} aria-current={k === step} onClick={() => onStep(k)}><span className="k">{t.kind}</span>{t.message}</li>)}
      </ol>
    </div>
  );
}
