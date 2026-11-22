"""Geospatial helpers. Distances in metres via a local equirectangular projection,
which is accurate to well under a metre at corridor scale."""
from __future__ import annotations

import math

from shapely.geometry import LineString, Point

EARTH_R = 6_371_008.8


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_R * math.asin(math.sqrt(a))


def _project(lat0: float, lon: float, lat: float) -> tuple[float, float]:
    x = math.radians(lon) * EARTH_R * math.cos(math.radians(lat0))
    y = math.radians(lat) * EARTH_R
    return x, y


def distance_to_route_m(lat: float, lon: float, geometry: list[tuple[float, float]]) -> float:
    """Shortest distance in metres from a point to a route polyline of (lon, lat)."""
    if not geometry:
        raise ValueError("empty route geometry")
    lat0 = sum(p[1] for p in geometry) / len(geometry)
    pts = [_project(lat0, lo, la) for lo, la in geometry]
    point = Point(*_project(lat0, lon, lat))
    if len(pts) == 1:
        return point.distance(Point(*pts[0]))
    return point.distance(LineString(pts))


def route_bbox(geometry: list[tuple[float, float]], pad_m: float) -> tuple[float, float, float, float]:
    """(min_lon, min_lat, max_lon, max_lat) padded by pad_m."""
    lons = [p[0] for p in geometry]
    lats = [p[1] for p in geometry]
    lat0 = sum(lats) / len(lats)
    dlat = math.degrees(pad_m / EARTH_R)
    dlon = math.degrees(pad_m / (EARTH_R * math.cos(math.radians(lat0))))
    return min(lons) - dlon, min(lats) - dlat, max(lons) + dlon, max(lats) + dlat
