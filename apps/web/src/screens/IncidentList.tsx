import type { Item, Kind, Severity } from "../api/types";
import { SEVERITIES } from "../api/types";
import { BasisBadge, CategoryChip, DemoTag, KIND_LABEL, SeverityBadge } from "../design/Badges";
import { ago, metres } from "../design/format";

export interface Filters { kinds: Set<Kind>; minSeverity: Severity; onlyRoutes: boolean }
export const defaultFilters = (): Filters => ({ kinds: new Set(), minSeverity: "info", onlyRoutes: false });

export function applyFilters(items: Item[], f: Filters): Item[] {
  return items.filter((i) =>
    (f.kinds.size === 0 || f.kinds.has(i.kind)) &&
    SEVERITIES.indexOf(i.severity) >= SEVERITIES.indexOf(f.minSeverity) &&
    (!f.onlyRoutes || i.onRoute));
}

export function FilterBar({ f, onChange }: { f: Filters; onChange: (f: Filters) => void }) {
  const kinds: Kind[] = ["pothole", "road_damage", "closure", "construction"];
  return (
    <div className="filters">
      {kinds.map((k) => (
        <button key={k} className="chip" aria-pressed={f.kinds.has(k)}
          onClick={() => { const n = new Set(f.kinds); n.has(k) ? n.delete(k) : n.add(k); onChange({ ...f, kinds: n }); }}>
          {KIND_LABEL[k]}
        </button>
      ))}
      <select className="select" aria-label="Minimum severity" value={f.minSeverity}
        onChange={(e) => onChange({ ...f, minSeverity: e.target.value as Severity })}>
        {SEVERITIES.map((s) => <option key={s} value={s}>{s === "info" ? "Any severity" : `${s[0].toUpperCase() + s.slice(1)} and above`}</option>)}
      </select>
      <label className="check"><input type="checkbox" checked={f.onlyRoutes} onChange={(e) => onChange({ ...f, onlyRoutes: e.target.checked })} /> My routes only</label>
    </div>
  );
}

function Row({ it, selected, onSelect }: { it: Item; selected: boolean; onSelect: () => void }) {
  return (
    <button className="row" aria-current={selected} onClick={onSelect}>
      <div className="row-top">
        <span className="row-title">{KIND_LABEL[it.kind]}{it.description ? ` — ${it.description}` : ""}</span>
        <SeverityBadge s={it.severity} />
      </div>
      <div className="row-sub">
        <BasisBadge b={it.basis} />
        {it.simulated && <DemoTag />}
        {it.distanceM !== null && <span className="mono">{metres(it.distanceM)} from route</span>}
        <span>{ago(it.observedAt)}</span>
      </div>
    </button>
  );
}

export default function IncidentList({ items, total, selectedId, onSelect, loading, error, onRetry }: {
  items: Item[]; total: number; selectedId: string | null; onSelect: (id: string) => void;
  loading: boolean; error: string | null; onRetry: () => void;
}) {
  if (error) return <div className="state"><p className="err">Can't reach the RoadTrust service.</p><p className="faint">{error}</p><button className="btn" onClick={onRetry}>Try again</button></div>;
  if (loading) return <div>{[0, 1, 2].map((i) => <div key={i} className="skel" />)}</div>;
  if (total === 0) return <div className="state">No active road incidents. We'll flag anything that appears near your routes.</div>;
  if (items.length === 0) return <div className="state">Nothing matches these filters.</div>;
  const on = items.filter((i) => i.onRoute);
  const off = items.filter((i) => !i.onRoute);
  const group = (title: string, list: Item[]) => list.length > 0 && (
    <section>
      <div className="group-title">{title} ({list.length})</div>
      {list.map((it) => <Row key={it.id} it={it} selected={it.id === selectedId} onSelect={() => onSelect(it.id)} />)}
    </section>
  );
  return <div>{group("On your routes", on)}{group("Elsewhere nearby", off)}</div>;
}
