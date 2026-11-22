import { log } from "./logger";

const NOMINATIM = "https://nominatim.openstreetmap.org/reverse";

// Simple in-memory cache: "lat2,lng2" → neighbourhood name
const _cache = new Map<string, string>();

function cacheKey(lat: number, lng: number): string {
  return `${lat.toFixed(2)},${lng.toFixed(2)}`;
}

export async function reverseGeocode(lat: number, lng: number): Promise<string> {
  const key = cacheKey(lat, lng);
  if (_cache.has(key)) return _cache.get(key)!;

  try {
    const url = `${NOMINATIM}?lat=${lat}&lon=${lng}&format=json&zoom=14`;
    const res = await fetch(url, {
      headers: { "User-Agent": "NammaPulse-WaterWatch/1.0" },
      signal: AbortSignal.timeout(5000),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = (await res.json()) as { address?: Record<string, string>; display_name?: string };

    const addr = data.address ?? {};
    // Try neighbourhood → suburb → city_district → county → city in order
    const name =
      addr.neighbourhood ||
      addr.suburb ||
      addr.city_district ||
      addr.county ||
      addr.city ||
      (data.display_name?.split(",")[0] ?? "your area");

    _cache.set(key, name);
    return name;
  } catch (err: unknown) {
    log("warn", "[reverseGeocode] failed, using fallback", {
      lat,
      lng,
      err: String(err),
    });
    return "your area";
  }
}
