"""Small geo helpers with no heavy dependencies. Distances in metres (local equirectangular projection)."""
from __future__ import annotations

import math

R = 6_371_008.8


def hav(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def _xy(lat0: float, lon: float, lat: float) -> tuple[float, float]:
    return math.radians(lon) * R * math.cos(math.radians(lat0)), math.radians(lat) * R


def dist_to_route_m(lat: float, lon: float, geometry: list[tuple[float, float]]) -> float:
    """Distance from a point to a polyline of (lon, lat)."""
    lat0 = sum(p[1] for p in geometry) / len(geometry)
    px, py = _xy(lat0, lon, lat)
    pts = [_xy(lat0, lo, la) for lo, la in geometry]
    if len(pts) == 1:
        return math.hypot(px - pts[0][0], py - pts[0][1])
    best = float("inf")
    for (ax, ay), (bx, by) in zip(pts, pts[1:]):
        dx, dy = bx - ax, by - ay
        seg = dx * dx + dy * dy
        t = 0.0 if seg == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / seg))
        best = min(best, math.hypot(px - (ax + t * dx), py - (ay + t * dy)))
    return best


def bbox_of(routes: list[list[tuple[float, float]]], pad_m: float) -> tuple[float, float, float, float]:
    """(min_lon, min_lat, max_lon, max_lat) around all routes, padded."""
    lons = [p[0] for g in routes for p in g]
    lats = [p[1] for g in routes for p in g]
    lat0 = sum(lats) / len(lats)
    dlat = math.degrees(pad_m / R)
    dlon = math.degrees(pad_m / (R * math.cos(math.radians(lat0))))
    return min(lons) - dlon, min(lats) - dlat, max(lons) + dlon, max(lats) + dlat


def grid_points(bbox: tuple[float, float, float, float], spacing_m: float) -> tuple[list[list[tuple[float, float]]], float, float]:
    """Rows of (lat, lon) grid centres covering the bbox. Returns (rows, dlat_deg, dlon_deg)."""
    min_lon, min_lat, max_lon, max_lat = bbox
    lat0 = (min_lat + max_lat) / 2
    dlat = math.degrees(spacing_m / R)
    dlon = math.degrees(spacing_m / (R * math.cos(math.radians(lat0))))
    rows, lat = [], min_lat
    while lat <= max_lat:
        row, lon = [], min_lon
        while lon <= max_lon:
            row.append((round(lat, 6), round(lon, 6)))
            lon += dlon
        rows.append(row)
        lat += dlat
    return rows, dlat, dlon
