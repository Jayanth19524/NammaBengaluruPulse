import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { buildItems, getHealth, getIncidents, investigate } from "./api/client";
import MapView from "./map/MapView";
import AgentStatus from "./screens/AgentStatus";
import IncidentDetail from "./screens/IncidentDetail";
import IncidentList, { applyFilters, defaultFilters, FilterBar } from "./screens/IncidentList";
import ReportForm from "./screens/ReportForm";
import TripPanel, { type Pt, type Stage } from "./screens/TripPanel";
import type { TripPlan } from "./api/types";
import { ago } from "./design/format";

type Tab = "incidents" | "trip" | "agent";

export default function App() {
  const [params, setParams] = useSearchParams();
  const selectedId = params.get("incident");
  const [tab, setTab] = useState<Tab>("incidents");
  const [reporting, setReporting] = useState(false);
  const [picked, setPicked] = useState<{ lat: number; lon: number } | null>(null);
  const [filters, setFilters] = useState(defaultFilters);
  const [origin, setOrigin] = useState<Pt | null>(null);
  const [dest, setDest] = useState<Pt | null>(null);
  const [stage, setStage] = useState<Stage>(null);
  const [plan, setPlan] = useState<TripPlan | null>(null);
  const [routeId, setRouteId] = useState<string | null>(null);
  const picking = reporting || (tab === "trip" && stage !== null);
  const onPick = (lat: number, lon: number) => {
    if (reporting) return setPicked({ lat, lon });
    if (stage === "origin") { setOrigin({ lat, lon }); setStage(dest ? null : "dest"); }
    else if (stage === "dest") { setDest({ lat, lon }); setStage(null); }
  };
  const pins = reporting ? (picked ? [{ ...picked }] : []) : tab === "trip"
    ? [...(origin ? [{ ...origin, color: "#2f9e5b" }] : []), ...(dest ? [{ ...dest, color: "#d12b2b" }] : [])] : [];
  const tripLines = tab === "trip" && plan ? plan.routes.map((r) => ({ id: r.id, geometry: r.geometry, selected: r.id === routeId })) : [];
  const tripKey = plan ? plan.routes.map((r) => r.id + r.geometry.length).join("|") + (origin?.lat ?? "") + (dest?.lat ?? "") : "";

  const inv = useQuery({ queryKey: ["investigate"], queryFn: investigate, refetchInterval: 60_000 });
  // Re-fetched after each investigation, since investigating is what ingests new source data.
  const inc = useQuery({ queryKey: ["incidents", inv.dataUpdatedAt], queryFn: getIncidents, placeholderData: (prev) => prev });
  const health = useQuery({ queryKey: ["health"], queryFn: getHealth });

  const items = useMemo(() => buildItems(inc.data ?? [], inv.data), [inc.data, inv.data]);
  const visible = useMemo(() => applyFilters(items, filters), [items, filters]);
  const selected = items.find((i) => i.id === selectedId) ?? null;
  const select = (id: string | null) => setParams(id ? { incident: id } : {}, { replace: false });

  useEffect(() => {
    const h = (e: Event) => setPicked((e as CustomEvent).detail);
    window.addEventListener("np-pick", h);
    return () => window.removeEventListener("np-pick", h);
  }, []);

  const failed = inv.isError || inc.isError;
  const degraded = inv.data?.source_health.some((s) => s.status === "degraded");

  return (
    <div className="app">
      <aside className="panel">
        <div className="panel-head">
          <div className="brand">NammaPulse</div>
          <div className="status" role="status">
            <span className={`dot ${failed || degraded ? "warn" : ""}`} />
            {failed ? "Service unreachable" : degraded ? "Monitoring, some sources unavailable" : "Monitoring"}
            {inv.dataUpdatedAt > 0 && !failed && <span className="faint">· last check {ago(new Date(inv.dataUpdatedAt).toISOString())}</span>}
          </div>
          <div className="tabs" role="tablist">
            <button className="tab" role="tab" aria-selected={tab === "incidents"} onClick={() => { setTab("incidents"); setReporting(false); }}>Road incidents</button>
            <button className="tab" role="tab" aria-selected={tab === "trip"} onClick={() => { setTab("trip"); setReporting(false); select(null); }}>Trip</button>
            <button className="tab" role="tab" aria-selected={tab === "agent"} onClick={() => { setTab("agent"); setReporting(false); }}>Agent</button>
          </div>
        </div>
        <div className="panel-body">
          {reporting ? (
            <ReportForm picked={picked} onCancel={() => { setReporting(false); setPicked(null); }}
              onDone={(id) => { setReporting(false); setPicked(null); setTab("incidents"); select(id); }} />
          ) : tab === "trip" ? (
            <TripPanel origin={origin} dest={dest} stage={stage} setStage={setStage} onPlan={setPlan}
              onClear={() => { setOrigin(null); setDest(null); setPlan(null); setStage(null); setRouteId(null); }}
              selectedRoute={routeId} setSelectedRoute={setRouteId} />
          ) : tab === "agent" ? (
            <AgentStatus health={health.data} inv={inv.data} />
          ) : selected ? (
            <IncidentDetail it={selected} onBack={() => select(null)} />
          ) : (
            <>
              <FilterBar f={filters} onChange={setFilters} />
              <IncidentList items={visible} total={items.length} selectedId={selectedId} onSelect={select}
                loading={inc.isLoading || inv.isLoading} error={failed ? String((inv.error ?? inc.error)) : null}
                onRetry={() => { inv.refetch(); inc.refetch(); }} />
            </>
          )}
        </div>
        {!reporting && tab === "incidents" && (
          <div className="panel-foot"><button className="btn primary block" onClick={() => { setReporting(true); select(null); }}>Report a road problem</button></div>
        )}
      </aside>
      <MapView items={tab === "trip" ? [] : visible} selectedId={selectedId} onSelect={select} picking={picking} onPick={onPick}
        pins={pins} trip={tripLines} tripKey={tripKey} />
    </div>
  );
}
