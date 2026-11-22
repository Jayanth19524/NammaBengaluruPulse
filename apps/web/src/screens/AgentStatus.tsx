import type { Health, InvestigateResult } from "../api/types";
import { DemoTag } from "../design/Badges";

export default function AgentStatus({ health, inv }: { health?: Health; inv?: InvestigateResult }) {
  return (
    <div className="detail">
      <h2>RoadTrust</h2>
      <p className="muted">Watches road damage, closures and construction near your routes.</p>
      <dl className="kv">
        <dt>Photo analysis</dt>
        <dd>{health ? (health.detector_available ? `Running (${health.detector})` : "Off. No detection model is configured, so photos are stored but not analysed.") : "Checking…"}</dd>
        <dt>Last investigation</dt>
        <dd>{inv ? `${inv.audit.routes} routes, ${inv.audit.active_incidents} active incidents, ${inv.audit.relevant} relevant to you` : "—"}</dd>
      </dl>
      <strong>Data sources</strong>
      <ul className="evidence">
        {(inv?.source_health ?? []).map((s) => (
          <li key={s.source}>
            <div className="row-top"><span className="row-title">{s.source}</span>{s.simulated && <DemoTag />}<span className={s.status === "ok" ? "" : "err"}>{s.status === "ok" ? "OK" : "Unavailable"}</span></div>
            {s.error && <div className="faint">{s.error}</div>}
          </li>
        ))}
        {!inv && <li className="faint">No data yet.</li>}
      </ul>
      {inv?.source_health.some((s) => s.simulated) && <div className="note">Some incidents come from a demo feed and are labelled as demo data.</div>}
    </div>
  );
}
