import { useMutation } from "@tanstack/react-query";
import { ScanResult } from "../types";

async function scanArea(lat: number, lng: number, radius: number): Promise<ScanResult> {
  const res = await fetch("/api/water/scan", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ lat, lng, radius }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as { error?: string }).error ?? `HTTP ${res.status}`);
  }
  return res.json() as Promise<ScanResult>;
}

export function useScanWater() {
  return useMutation({
    mutationFn: ({
      lat,
      lng,
      radius,
    }: {
      lat: number;
      lng: number;
      radius: number;
    }) => scanArea(lat, lng, radius),
  });
}
