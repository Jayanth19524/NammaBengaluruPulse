import maplibregl, { type GeoJSONSource } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { useEffect, useRef, useState } from "react";
import type { Item, Severity } from "../api/types";
import { DEMO_ROUTES, MAP_CENTER } from "../demo";

const STYLE = "https://tiles.openfreemap.org/styles/liberty"; // free vector tiles with 3D buildings, no key
const HEIGHT: Record<Severity, number> = { info: 10, low: 25, moderate: 50, high: 80, critical: 120 };
const SEVS: Severity[] = ["info", "low", "moderate", "high", "critical"];

const css = (name: string) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
const sevColors = () => Object.fromEntries(SEVS.map((s) => [s, css(`--sev-${s}`)])) as Record<Severity, string>;

type FC = GeoJSON.FeatureCollection;
const empty: FC = { type: "FeatureCollection", features: [] };

function incidentCollections(items: Item[]): { points: FC; columns: FC } {
  const points: GeoJSON.Feature[] = [];
  const columns: GeoJSON.Feature[] = [];
  for (const it of items) {
    const props = { id: it.id, severity: it.severity, h: HEIGHT[it.severity] };
    points.push({ type: "Feature", properties: props, geometry: { type: "Point", coordinates: [it.lon, it.lat] } });
    const dLat = 6 / 111320, dLon = 6 / (111320 * Math.cos((it.lat * Math.PI) / 180));
    const ring = [[it.lon - dLon, it.lat - dLat], [it.lon + dLon, it.lat - dLat], [it.lon + dLon, it.lat + dLat], [it.lon - dLon, it.lat + dLat], [it.lon - dLon, it.lat - dLat]];
    columns.push({ type: "Feature", properties: props, geometry: { type: "Polygon", coordinates: [ring] } });
  }
  return { points: { type: "FeatureCollection", features: points }, columns: { type: "FeatureCollection", features: columns } };
}

const routesCollection = (): FC => ({
  type: "FeatureCollection",
  features: DEMO_ROUTES.map((r) => ({ type: "Feature", properties: { id: r.id, name: r.name }, geometry: { type: "LineString", coordinates: r.geometry } })),
});

interface Props {
  items: Item[]; selectedId: string | null; onSelect: (id: string | null) => void;
  picking: boolean; picked: { lat: number; lon: number } | null; onPick: (lat: number, lon: number) => void;
}

export default function MapView({ items, selectedId, onSelect, picking, picked, onPick }: Props) {
  const el = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const markerRef = useRef<maplibregl.Marker | null>(null);
  const [ready, setReady] = useState(false);
  const [is3d, setIs3d] = useState(true);
  // Latest callbacks/state for handlers registered once.
  const live = useRef({ onSelect, onPick, picking });
  live.current = { onSelect, onPick, picking };

  useEffect(() => {
    if (!el.current) return;
    const map = new maplibregl.Map({ container: el.current, style: STYLE, center: MAP_CENTER, zoom: 15.2, pitch: 62, bearing: -18, maxPitch: 80, attributionControl: { compact: true } });
    mapRef.current = map;
    map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), "top-right");
    map.on("load", () => {
      const accent = css("--accent");
      const colors = sevColors();
      const sevMatch: maplibregl.ExpressionSpecification = ["match", ["get", "severity"], ...SEVS.flatMap((s) => [s, colors[s]]), colors.info] as never;
      map.addSource("routes", { type: "geojson", data: routesCollection() });
      map.addSource("points", { type: "geojson", data: empty });
      map.addSource("columns", { type: "geojson", data: empty });
      // Corridor drawn at true metres: width doubles per zoom level.
      map.addLayer({ id: "corridor", type: "line", source: "routes", layout: { "line-cap": "round" }, paint: { "line-color": accent, "line-opacity": 0.24, "line-width": ["interpolate", ["exponential", 2], ["zoom"], 10, 0.67, 20, 684] } });
      map.addLayer({ id: "route", type: "line", source: "routes", layout: { "line-cap": "round", "line-join": "round" }, paint: { "line-color": accent, "line-width": 3.5 } });
      map.addLayer({ id: "columns", type: "fill-extrusion", source: "columns", paint: { "fill-extrusion-color": sevMatch, "fill-extrusion-height": ["get", "h"], "fill-extrusion-opacity": 0.92 } });
      map.addLayer({ id: "pts", type: "circle", source: "points", paint: { "circle-radius": 6, "circle-color": sevMatch, "circle-stroke-color": "#ffffff", "circle-stroke-width": 2, "circle-pitch-alignment": "map" } });
      map.addLayer({ id: "sel", type: "circle", source: "points", filter: ["==", ["get", "id"], ""], paint: { "circle-radius": 13, "circle-color": "rgba(0,0,0,0)", "circle-stroke-color": css("--text"), "circle-stroke-width": 2, "circle-pitch-alignment": "map" } });
      for (const layer of ["pts", "columns"]) {
        map.on("mouseenter", layer, () => { if (!live.current.picking) map.getCanvas().style.cursor = "pointer"; });
        map.on("mouseleave", layer, () => { map.getCanvas().style.cursor = live.current.picking ? "crosshair" : ""; });
        map.on("click", layer, (e) => {
          if (live.current.picking) return;
          const id = e.features?.[0]?.properties?.id as string | undefined;
          if (id) { live.current.onSelect(id); e.originalEvent.stopPropagation(); }
        });
      }
      map.on("click", (e) => {
        if (live.current.picking) live.current.onPick(e.lngLat.lat, e.lngLat.lng);
      });
      setReady(true);
    });
    return () => { map.remove(); mapRef.current = null; };
  }, []);

  // Data -> map
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    const { points, columns } = incidentCollections(items);
    (map.getSource("points") as GeoJSONSource).setData(points);
    (map.getSource("columns") as GeoJSONSource).setData(columns);
  }, [items, ready]);

  // Selection -> highlight + camera
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    map.setFilter("sel", ["==", ["get", "id"], selectedId ?? ""]);
    const it = items.find((i) => i.id === selectedId);
    if (it) map.easeTo({ center: [it.lon, it.lat], zoom: Math.max(map.getZoom(), 16.2), duration: 700 });
  }, [selectedId, ready]); // eslint-disable-line react-hooks/exhaustive-deps

  // Picking mode: cursor and marker
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    map.getCanvas().style.cursor = picking ? "crosshair" : "";
  }, [picking, ready]);
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    markerRef.current?.remove();
    markerRef.current = null;
    if (picked && picking) markerRef.current = new maplibregl.Marker({ color: css("--accent") }).setLngLat([picked.lon, picked.lat]).addTo(map);
  }, [picked, picking, ready]);

  function setView(three: boolean) {
    setIs3d(three);
    mapRef.current?.easeTo({ pitch: three ? 62 : 0, bearing: three ? -18 : 0, duration: 600 });
  }

  return (
    <div className="mapwrap">
      <div ref={el} className="map" role="application" aria-label="3D map of incidents and monitored routes" />
      <div className="float viewtoggle" role="group" aria-label="Map view">
        <button aria-pressed={is3d} onClick={() => setView(true)}>3D</button>
        <button aria-pressed={!is3d} onClick={() => setView(false)}>2D</button>
      </div>
      {picking && <div className="float pickhint">Click the map to set the location</div>}
      <div className="float legend" aria-label="Legend">
        <div className="li"><i /> Monitored route</div>
        <div className="li"><i className="corr" /> Monitoring corridor</div>
        <div className="li">Column height shows severity</div>
      </div>
    </div>
  );
}
