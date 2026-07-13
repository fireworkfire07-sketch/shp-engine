"""Stage 5: Background Cleanup.

Partially real implementation, scoped conservatively:

  * DETECTION is real: MediaPipe's EfficientDet-Lite object detector
    (COCO-80 classes), lazily downloaded and cached like Stage 3's pose
    model. It flags common background distractions that have a COCO
    class - people other than the main subject, cars/trucks/buses,
    bottles, bags/suitcases, bicycles/motorcycles, traffic signs/lights.
  * REMOVAL is real but deliberately limited to small, isolated
    detections (below `MAX_AUTO_REMOVE_AREA_FRACTION` of the frame, and
    not overlapping the main subject) via cv2.inpaint - the same
    conservative approach as Stage 8's spot removal. Anything larger is
    only flagged, never auto-removed, because classical inpainting over a
    large area produces visible smearing - exactly the "damage the
    subject / break realism" outcome the spec forbids. A trained
    generative inpainting model would be a drop-in replacement for
    `_remove_object` without changing anything else in this stage.

NOT detectable at all with an object-class detector (documented gaps that
need different techniques entirely):
  * generic "trash" (no COCO class covers loose litter)
  * power lines (needs line/wire segmentation, not object detection)
  * unwanted shadows / reflections (needs lighting-aware segmentation)
  * generic "street signs" beyond the specific "stop sign" COCO class
"""

from __future__ import annotations

import os
import urllib.request
from dataclasses import dataclass, field

import cv2
import numpy as np

from ..models import FaceReport

MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/object_detector/"
    "efficientdet_lite0/int8/latest/efficientdet_lite0.tflite"
)
MODEL_CACHE_PATH = os.path.expanduser(
    "~/.cache/photographer_ai/models/efficientdet_lite0.tflite"
)

DISTRACTION_LABELS = {
    "person", "car", "truck", "bus", "bottle", "backpack", "handbag",
    "suitcase", "bicycle", "motorcycle", "stop sign", "traffic light",
}
SCORE_THRESHOLD = 0.4
MAX_AUTO_REMOVE_AREA_FRACTION = 0.015  # only auto-remove small distractions

_detector = None
_load_failed = False
_load_failure_reason = ""


@dataclass
class DistractionInfo:
    label: str
    bbox: tuple           # x, y, w, h
    score: float
    auto_removed: bool = False


@dataclass
class BackgroundReport:
    implemented: bool
    distractions: list = field(default_factory=list)   # list[DistractionInfo]
    note: str = ""


def _get_detector():
    global _detector, _load_failed, _load_failure_reason
    if _detector is not None or _load_failed:
        return _detector
    try:
        import mediapipe as mp
        from mediapipe.tasks import python as mp_python
        from mediapipe.tasks.python import vision

        os.makedirs(os.path.dirname(MODEL_CACHE_PATH), exist_ok=True)
        if not os.path.exists(MODEL_CACHE_PATH):
            urllib.request.urlretrieve(MODEL_URL, MODEL_CACHE_PATH)

        base_options = mp_python.BaseOptions(model_asset_path=MODEL_CACHE_PATH)
        options = vision.ObjectDetectorOptions(
            base_options=base_options, score_threshold=SCORE_THRESHOLD, max_results=20
        )
        _detector = vision.ObjectDetector.create_from_options(options)
    except Exception as exc:  # noqa: BLE001
        _load_failed = True
        _load_failure_reason = str(exc)
        _detector = None
    return _detector


def clean_background(rgb: np.ndarray, faces: FaceReport) -> tuple:
    """Returns (possibly-edited RGB array, BackgroundReport)."""
    detector = _get_detector()
    if detector is None:
        return rgb, BackgroundReport(
            implemented=False,
            note=(
                "Object detector unavailable (no network on first run, or "
                f"missing native runtime libs). Detail: {_load_failure_reason}"
            ),
        )

    import mediapipe as mp

    h, w = rgb.shape[:2]
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
    result = detector.detect(mp_image)

    subject_boxes = [f.bbox for f in faces.faces]
    out = rgb.copy()
    distractions = []

    for det in result.detections:
        category = det.categories[0]
        label = category.category_name
        if label not in DISTRACTION_LABELS:
            continue

        bb = det.bounding_box
        bbox = (bb.origin_x, bb.origin_y, bb.width, bb.height)
        if _overlaps_subject(bbox, subject_boxes):
            continue  # this is the main subject, not a distraction

        area_fraction = (bb.width * bb.height) / (w * h)
        auto_removed = False
        if area_fraction <= MAX_AUTO_REMOVE_AREA_FRACTION:
            out = _remove_object(out, bbox)
            auto_removed = True

        distractions.append(DistractionInfo(
            label=label, bbox=bbox, score=float(category.score), auto_removed=auto_removed,
        ))

    return out, BackgroundReport(implemented=True, distractions=distractions)


def _overlaps_subject(bbox: tuple, subject_boxes: list) -> bool:
    x, y, w, h = bbox
    for sx, sy, sw, sh in subject_boxes:
        ix0, iy0 = max(x, sx), max(y, sy)
        ix1, iy1 = min(x + w, sx + sw), min(y + h, sy + sh)
        if ix1 > ix0 and iy1 > iy0:
            return True
    return False


def _remove_object(rgb: np.ndarray, bbox: tuple) -> np.ndarray:
    x, y, w, h = bbox
    h_img, w_img = rgb.shape[:2]
    x0, y0 = max(0, x), max(0, y)
    x1, y1 = min(w_img, x + w), min(h_img, y + h)
    if x1 <= x0 or y1 <= y0:
        return rgb

    mask = np.zeros((h_img, w_img), dtype=np.uint8)
    mask[y0:y1, x0:x1] = 255

    bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    inpainted_bgr = cv2.inpaint(bgr, mask, inpaintRadius=5, flags=cv2.INPAINT_TELEA)
    return cv2.cvtColor(inpainted_bgr, cv2.COLOR_BGR2RGB)
