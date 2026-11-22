"""GPS extraction and validation for uploaded photos and client-supplied coordinates."""
from __future__ import annotations

import io

from PIL import ExifTags, Image

from .config import CityConfig


class GpsError(ValueError):
    pass


def _to_deg(value, ref) -> float:
    d, m, s = (float(x) for x in value)
    deg = d + m / 60 + s / 3600
    return -deg if ref in ("S", "W") else deg


def exif_gps(image_bytes: bytes) -> tuple[float, float] | None:
    """Return (lat, lon) from EXIF, or None if the image has no usable GPS tags."""
    try:
        img = Image.open(io.BytesIO(image_bytes))
        gps = img.getexif().get_ifd(ExifTags.IFD.GPSInfo)
    except Exception:
        return None
    if not gps:
        return None
    try:
        lat = _to_deg(gps[2], gps[1])
        lon = _to_deg(gps[4], gps[3])
    except (KeyError, TypeError, ValueError, ZeroDivisionError):
        return None
    return lat, lon


def validate_coordinates(lat: float | None, lon: float | None, city: CityConfig) -> tuple[float, float]:
    if lat is None or lon is None:
        raise GpsError("coordinates missing")
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise GpsError("coordinates out of range")
    if lat == 0 and lon == 0:
        raise GpsError("null island (0,0) is not a valid location")
    if not city.contains(lat, lon):
        raise GpsError(f"location is outside the {city.name} coverage area")
    return lat, lon
