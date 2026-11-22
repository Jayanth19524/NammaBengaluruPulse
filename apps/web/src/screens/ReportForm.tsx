import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { postReport } from "../api/client";
import type { Kind, ReportResult, Severity } from "../api/types";
import { SEVERITIES } from "../api/types";
import { KIND_LABEL } from "../design/Badges";

function analysisText(r: ReportResult, hadImage: boolean): string {
  if (!hadImage) return "Reported without a photo.";
  if (!r.analysis.cv_run) return "Photo saved. No detection model is running, so it was not analysed.";
  return r.analysis.result === "damage_detected" ? "Photo analysed: damage detected." : "Photo analysed: no damage detected. Your report was still kept.";
}

export default function ReportForm({ picked, onCancel, onDone }: {
  picked: { lat: number; lon: number } | null; onCancel: () => void; onDone: (id: string) => void;
}) {
  const qc = useQueryClient();
  const [kind, setKind] = useState<Kind>("pothole");
  const [severity, setSeverity] = useState<Severity>("low");
  const [description, setDescription] = useState("");
  const [image, setImage] = useState<File | null>(null);
  const [result, setResult] = useState<ReportResult | null>(null);
  const m = useMutation({
    mutationFn: () => postReport({ lat: picked!.lat, lon: picked!.lon, kind, severity, description, image }),
    onSuccess: (r) => { setResult(r); qc.invalidateQueries({ queryKey: ["incidents"] }); qc.invalidateQueries({ queryKey: ["investigate"] }); },
  });

  if (result) {
    return (
      <div className="form">
        <strong>{result.created ? "Report added" : "Merged with an existing report nearby"}</strong>
        <p className="muted">{analysisText(result, !!image)}</p>
        <p className="muted">It is listed as reported, not verified.</p>
        <button className="btn primary" onClick={() => onDone(result.incident.id)}>View on map</button>
      </div>
    );
  }
  return (
    <form className="form" onSubmit={(e) => { e.preventDefault(); if (picked) m.mutate(); }}>
      <strong>Report a road problem</strong>
      <div className="loc">
        {picked ? <span className="mono">{picked.lat.toFixed(5)}, {picked.lon.toFixed(5)}</span> : <span className="muted">Click the map to set the location.</span>}
        <div><button type="button" className="linkbtn" onClick={() => navigator.geolocation?.getCurrentPosition(
          (p) => onPickCurrent(p.coords.latitude, p.coords.longitude), () => undefined)}>Use my current location</button></div>
      </div>
      <div className="field"><label htmlFor="kind">Type</label>
        <select id="kind" className="input" value={kind} onChange={(e) => setKind(e.target.value as Kind)}>
          {(["pothole", "road_damage", "closure", "construction", "other"] as Kind[]).map((k) => <option key={k} value={k}>{KIND_LABEL[k]}</option>)}
        </select></div>
      <div className="field"><label htmlFor="sev">How bad is it?</label>
        <select id="sev" className="input" value={severity} onChange={(e) => setSeverity(e.target.value as Severity)}>
          {SEVERITIES.map((s) => <option key={s} value={s}>{s[0].toUpperCase() + s.slice(1)}</option>)}
        </select></div>
      <div className="field"><label htmlFor="desc">Details (optional)</label>
        <textarea id="desc" className="input" value={description} onChange={(e) => setDescription(e.target.value)} /></div>
      <div className="field"><label htmlFor="img">Photo (optional)</label>
        <input id="img" className="input" type="file" accept="image/*" onChange={(e) => setImage(e.target.files?.[0] ?? null)} /></div>
      {m.error && <div className="err">{(m.error as Error).message}</div>}
      <div style={{ display: "flex", gap: 8 }}>
        <button type="submit" className="btn primary" disabled={!picked || m.isPending}>{m.isPending ? "Sending…" : "Submit report"}</button>
        <button type="button" className="btn" onClick={onCancel}>Cancel</button>
      </div>
    </form>
  );
  function onPickCurrent(lat: number, lon: number) { window.dispatchEvent(new CustomEvent("np-pick", { detail: { lat, lon } })); }
}
