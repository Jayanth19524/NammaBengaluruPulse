import type { Item } from "../api/types";
import { BasisBadge, CategoryChip, DemoTag, KIND_LABEL, SeverityBadge } from "../design/Badges";
import { ago, metres } from "../design/format";
import { DEMO_ROUTES } from "../demo";

const REPAIR = { open: "Open", repair_reported: "Repair reported by users, not confirmed", repaired: "Repaired (official source)" } as const;

function evidenceLine(e: Record<string, unknown>): string {
  switch (e.type) {
    case "report_count": return `${e.count} distinct reporter${e.count === 1 ? "" : "s"}. ${e.note}`;
    case "cv_detection": return `Photo analysed by ${e.model}: ${(e.detections as unknown[]).length} detection(s).`;
    case "photo": return "Photo stored. It was not analysed because no detection model is running.";
    case "osm_way": return "OpenStreetMap way tagged as roadworks or restricted access.";
    case "repair_claim": return String(e.note);
    default: return String(e.type);
  }
}

export default function IncidentDetail({ it, onBack }: { it: Item; onBack: () => void }) {
  const route = DEMO_ROUTES.find((r) => r.id === it.routeId);
  return (
    <div className="detail">
      <button className="linkbtn" onClick={onBack}>&larr; All incidents</button>
      <h2>{KIND_LABEL[it.kind]}</h2>
      <div className="row-sub"><CategoryChip kind={it.kind} /><SeverityBadge s={it.severity} /><BasisBadge b={it.basis} />{it.simulated && <DemoTag />}</div>
      {it.description && <p>{it.description}</p>}
      <div className="action"><strong>What to do</strong><div>{it.action}</div></div>
      {it.basis === "reported" && <div className="note">Reported by the community. This has not been independently verified.</div>}
      <dl className="kv">
        <dt>Route</dt><dd>{route ? route.name : "Not on a monitored route"}</dd>
        {it.distanceM !== null && (<><dt>Distance</dt><dd className="mono">{metres(it.distanceM)} from route</dd></>)}
        <dt>Last seen</dt><dd>{ago(it.observedAt)}</dd>
        <dt>Confidence</dt><dd className="mono">{Math.round(it.confidence * 100)}%</dd>
        <dt>Repair status</dt><dd>{REPAIR[it.repairStatus]}</dd>
        <dt>Location</dt><dd className="mono">{it.lat.toFixed(5)}, {it.lon.toFixed(5)}</dd>
        <dt>Source</dt><dd>{it.sources.join(", ")}</dd>
      </dl>
      <strong>Evidence</strong>
      <ul className="evidence">{it.evidence.filter((e) => e.type !== "simulated").map((e, i) => <li key={i}>{evidenceLine(e)}</li>)}</ul>
    </div>
  );
}
