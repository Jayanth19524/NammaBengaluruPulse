"""Pothole detection. Real detection needs YOLO weights; without them we say so
instead of guessing."""
from __future__ import annotations

import io
import os
from typing import Protocol

from PIL import Image

from .models import Detection, DetectionResult


class Detector(Protocol):
    name: str
    available: bool

    def detect(self, image_bytes: bytes) -> DetectionResult: ...


class NullDetector:
    """Used when no model is configured. Returns available=False so callers never
    present a missing analysis as 'no damage found'."""
    name = "none"
    available = False

    def detect(self, image_bytes: bytes) -> DetectionResult:
        w = h = 0
        try:
            w, h = Image.open(io.BytesIO(image_bytes)).size
        except Exception:
            pass
        return DetectionResult(available=False, image_width=w, image_height=h,
                               note="No detection model configured; image stored without analysis.")


class YoloDetector:
    name = "yolo"
    available = True

    def __init__(self, weights: str, device: str | None = None):
        from ultralytics import YOLO  # lazy: heavy optional dependency

        self._model = YOLO(weights)
        self._device = device

    def detect(self, image_bytes: bytes) -> DetectionResult:
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        res = self._model.predict(img, verbose=False, device=self._device)[0]
        names = res.names
        dets = [
            Detection(label=names[int(b.cls)], confidence=float(b.conf), bbox=tuple(map(float, b.xyxy[0].tolist())))
            for b in res.boxes
        ]
        return DetectionResult(available=True, detections=dets, image_width=img.width, image_height=img.height)


def load_detector() -> Detector:
    weights = os.environ.get("ROADTRUST_YOLO_WEIGHTS")
    if not weights or not os.path.exists(weights):
        return NullDetector()
    try:
        return YoloDetector(weights)
    except Exception:  # ultralytics missing or weights unreadable
        return NullDetector()
