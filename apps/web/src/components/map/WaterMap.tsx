import React, { useCallback, useState, useRef, useEffect } from "react";
import {
  MapContainer,
  TileLayer,
  useMapEvents,
  Circle,
  Marker,
  Popup,
  useMap,
} from "react-leaflet";
import L from "leaflet";
import { Incident } from "../../types";
import { useScanWater } from "../../hooks/useScanWater";
import { IncidentDetailPanel } from "../panels/IncidentDetailPanel";
import { SeverityBadge } from "../panels/SeverityBadge";

// City config defaults — no hardcoded values in components
const CITY_CENTER: [number, number] = [12.9716, 77.5946]; // Bengaluru
const DEFAULT_ZOOM = 13;
const SCAN_RADIUS_M = 5000;

// Water drop marker icon
function makeWaterIcon(severity: string) {
  const colors: Record<string, string> = {
    critical: "#dc2626",
    high: "#ea580c",
    moderate: "#ca8a04",
    low: "#16a34a",
    info: "#6b7280",
  };
  const color = colors[severity] ?? "#0d9488";
  return L.divIcon({
    className: "",
    html: `<div style="
      width:20px;height:20px;
      background:${color};
      border:2px solid #fff;
      border-radius:50% 50% 50% 0;
      transform:rotate(-45deg);
      box-shadow:0 1px 4px rgba(0,0,0,0.25);
    "></div>`,
    iconSize: [20, 20],
    iconAnchor: [10, 20],
    popupAnchor: [0, -22],
  });
}

interface ClickHandlerProps {
  onMapClick: (lat: number, lng: number) => void;
}

function ClickHandler({ onMapClick }: ClickHandlerProps) {
  useMapEvents({
    click(e) {
      onMapClick(e.latlng.lat, e.latlng.lng);
    },
  });
  return null;
}

function FlyTo({ lat, lng }: { lat: number; lng: number }) {
  const map = useMap();
  useEffect(() => {
    map.flyTo([lat, lng], Math.max(map.getZoom(), 14), { duration: 0.8 });
  }, [lat, lng, map]);
  return null;
}

export function WaterMap() {
  const [scanPoint, setScanPoint] = useState<{ lat: number; lng: number } | null>(null);
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [selectedIncident, setSelectedIncident] = useState<Incident | null>(null);
  const { mutate: scan, isPending, isError, error } = useScanWater();

  const handleMapClick = useCallback(
    (lat: number, lng: number) => {
      setScanPoint({ lat, lng });
      setSelectedIncident(null);
      scan(
        { lat, lng, radius: SCAN_RADIUS_M },
        {
          onSuccess(data) {
            setIncidents(data.incidents);
          },
        }
      );
    },
    [scan]
  );

  return (
    <div className="relative w-full h-full flex">
      {/* Map */}
      <div className="flex-1 relative">
        {/* Scanning overlay */}
        {isPending && (
          <div className="absolute top-3 left-1/2 -translate-x-1/2 z-[1000] bg-white border border-border rounded-control px-3 py-1.5 text-sm text-gray-700 shadow-sm">
            Scanning area...
          </div>
        )}
        {isError && (
          <div className="absolute top-3 left-1/2 -translate-x-1/2 z-[1000] bg-white border border-red-200 rounded-control px-3 py-1.5 text-sm text-red-700 shadow-sm">
            Scan failed — {(error as Error)?.message ?? "unknown error"}
          </div>
        )}

        <MapContainer
          center={CITY_CENTER}
          zoom={DEFAULT_ZOOM}
          style={{ height: "100%", width: "100%" }}
          zoomControl={true}
        >
          {/* OpenTopoMap — free terrain tiles, no API key */}
          <TileLayer
            url="https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png"
            attribution='Map data: &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors, <a href="http://viewfinderpanoramas.org">SRTM</a> | Map style: &copy; <a href="https://opentopomap.org">OpenTopoMap</a>'
            maxZoom={17}
          />

          <ClickHandler onMapClick={handleMapClick} />
          {scanPoint && <FlyTo lat={scanPoint.lat} lng={scanPoint.lng} />}

          {/* Scan radius circle */}
          {scanPoint && (
            <Circle
              center={[scanPoint.lat, scanPoint.lng]}
              radius={SCAN_RADIUS_M}
              pathOptions={{
                color: "#0d9488",
                weight: 1.5,
                fillColor: "#0d9488",
                fillOpacity: 0.06,
              }}
            />
          )}

          {/* Incident markers */}
          {incidents.map((inc, i) => (
            <Marker
              key={inc.id ?? i}
              position={[inc.latitude, inc.longitude]}
              icon={makeWaterIcon(inc.severity)}
              eventHandlers={{ click: () => setSelectedIncident(inc) }}
            >
              <Popup>
                <div className="text-sm font-medium">{inc.area_name ?? "Water incident"}</div>
                <SeverityBadge severity={inc.severity} />
              </Popup>
            </Marker>
          ))}
        </MapContainer>

        {/* Click hint */}
        {!scanPoint && incidents.length === 0 && (
          <div className="pointer-events-none absolute bottom-6 left-1/2 -translate-x-1/2 z-[1000] bg-white/90 border border-border rounded-control px-4 py-2 text-sm text-gray-600">
            Click anywhere on the map to scan for water issues
          </div>
        )}

        {/* Empty state after scan */}
        {scanPoint && !isPending && incidents.length === 0 && !isError && (
          <div className="pointer-events-none absolute bottom-6 left-1/2 -translate-x-1/2 z-[1000] bg-white/90 border border-border rounded-control px-4 py-2 text-sm text-gray-600">
            No water disruptions found in this area.
          </div>
        )}
      </div>

      {/* Detail panel — right sidebar on desktop */}
      {selectedIncident && (
        <div className="w-80 border-l border-border bg-white flex-shrink-0 hidden md:flex flex-col">
          <IncidentDetailPanel
            incident={selectedIncident}
            onClose={() => setSelectedIncident(null)}
          />
        </div>
      )}

      {/* Detail panel — bottom sheet on mobile */}
      {selectedIncident && (
        <div className="md:hidden absolute bottom-0 left-0 right-0 z-[1001] max-h-[60vh] overflow-y-auto rounded-t-panel shadow-lg">
          <IncidentDetailPanel
            incident={selectedIncident}
            onClose={() => setSelectedIncident(null)}
          />
        </div>
      )}
    </div>
  );
}
