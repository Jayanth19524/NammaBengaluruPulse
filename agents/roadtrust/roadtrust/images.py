"""Image storage: strip EXIF, save to disk under a content-addressed key.

Privacy: GPS tags and all EXIF metadata are removed before saving.
If ROADTRUST_IMAGE_DIR is not set, images are accepted but discarded (safe default).
"""
from __future__ import annotations

import hashlib
import io
import os
from pathlib import Path

from PIL import Image


_DIR: Path | None = None


def _store_dir() -> Path | None:
    global _DIR
    if _DIR is not None:
        return _DIR
    d = os.environ.get("ROADTRUST_IMAGE_DIR")
    if not d:
        return None
    _DIR = Path(d)
    _DIR.mkdir(parents=True, exist_ok=True)
    return _DIR


def strip_exif(image_bytes: bytes) -> bytes:
    """Return a JPEG with all EXIF stripped. Raises ValueError on unreadable input."""
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85, exif=b"")
    return buf.getvalue()


def save_image(image_bytes: bytes) -> str | None:
    """Strip EXIF and save to disk. Returns the storage key (filename stem) or None
    if no image dir is configured. Identical content deduplicates by hash."""
    d = _store_dir()
    if d is None:
        return None
    cleaned = strip_exif(image_bytes)
    key = hashlib.sha256(cleaned).hexdigest()[:32]
    path = d / f"{key}.jpg"
    if not path.exists():
        path.write_bytes(cleaned)
    return key
