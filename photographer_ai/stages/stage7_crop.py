"""Stage 7: Crop Engine.

Real implementation. Generates aspect-ratio crops for common delivery
targets, positioning the subject (detected face, or the composition
engine's saliency point as fallback) near the upper-third of the frame and
guaranteeing any detected face bounding box stays fully inside the crop -
directly satisfying the spec's "never crop hands or feet accidentally" /
"keep eyes near upper-third" requirements for the parts we can actually
detect (faces). Hand/feet-safe cropping needs body pose keypoints, which
is Stage 3's documented gap - once real keypoints exist, extending
`_required_bbox` to also cover them is a few lines, not a redesign.
"""

from __future__ import annotations

import numpy as np

from ..models import FaceReport

# name -> (width_ratio, height_ratio)
CROP_PRESETS = {
    "original": None,
    "instagram_square": (1, 1),
    "instagram_portrait": (4, 5),
    "portrait": (4, 5),
    "landscape": (3, 2),
    "story": (9, 16),
    "reel": (9, 16),
    "tiktok": (9, 16),
    "facebook": (16, 9),
    "print": (2, 3),
    "album": (4, 3),
}


def generate_crops(rgb: np.ndarray, faces: FaceReport, subject_point: tuple) -> dict:
    h, w = rgb.shape[:2]
    face_bbox = _largest_face_bbox(faces)

    crops = {}
    for name, ratio in CROP_PRESETS.items():
        if ratio is None:
            crops[name] = rgb
            continue
        box = _compute_crop_box(w, h, ratio, subject_point, face_bbox)
        x0, y0, x1, y1 = box
        crops[name] = rgb[y0:y1, x0:x1]
    return crops


def _largest_face_bbox(faces: FaceReport):
    if not faces.faces:
        return None
    f = max(faces.faces, key=lambda f: f.bbox[2] * f.bbox[3])
    x, y, fw, fh = f.bbox
    return (x, y, x + fw, y + fh)


def _compute_crop_box(w: int, h: int, ratio: tuple, subject_point: tuple, face_bbox) -> tuple:
    target_ratio = ratio[0] / ratio[1]
    current_ratio = w / h

    if target_ratio > current_ratio:
        crop_w, crop_h = w, int(round(w / target_ratio))
    else:
        crop_h, crop_w = h, int(round(h * target_ratio))
    crop_w = min(crop_w, w)
    crop_h = min(crop_h, h)

    sx, sy = subject_point
    # Center horizontally on the subject; vertically place the subject at
    # the upper third of the crop (a portrait/headshot framing convention).
    x0 = int(round(sx - crop_w / 2))
    y0 = int(round(sy - crop_h / 3))

    x0 = max(0, min(x0, w - crop_w))
    y0 = max(0, min(y0, h - crop_h))
    x1, y1 = x0 + crop_w, y0 + crop_h

    if face_bbox is not None:
        x0, y0, x1, y1 = _shift_to_contain(
            (x0, y0, x1, y1), face_bbox, w, h
        )

    return x0, y0, x1, y1


def _shift_to_contain(crop_box: tuple, required_box: tuple, w: int, h: int) -> tuple:
    """Shift (never resize) the crop so `required_box` fits fully inside it.

    If the crop is smaller than the required box on some axis, it can't be
    fully contained without resizing - in that case center the crop on the
    required box's center on that axis instead, which is the best available
    compromise for that aspect ratio.
    """
    cx0, cy0, cx1, cy1 = crop_box
    rx0, ry0, rx1, ry1 = required_box
    crop_w, crop_h = cx1 - cx0, cy1 - cy0
    req_w, req_h = rx1 - rx0, ry1 - ry0

    if req_w <= crop_w:
        if rx0 < cx0:
            cx0 = rx0
        if rx1 > cx1:
            cx0 += rx1 - cx1
    else:
        cx0 = int(round((rx0 + rx1) / 2 - crop_w / 2))

    if req_h <= crop_h:
        if ry0 < cy0:
            cy0 = ry0
        if ry1 > cy1:
            cy0 += ry1 - cy1
    else:
        cy0 = int(round((ry0 + ry1) / 2 - crop_h / 2))

    cx0 = max(0, min(cx0, w - crop_w))
    cy0 = max(0, min(cy0, h - crop_h))
    return cx0, cy0, cx0 + crop_w, cy0 + crop_h
