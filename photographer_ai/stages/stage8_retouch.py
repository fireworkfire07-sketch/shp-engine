"""Stage 8: Portrait Retouch.

Real, working spot-removal implementation - not a full frequency-separation
retouch suite, but a genuine, bounded technique:

  1. restrict all work to detected face bounding boxes (Stage 2) so hair,
     clothing and background are never touched
  2. find small blemish-like spots via a morphological top-hat/black-hat
     transform (isolates features much smaller than the face itself -
     typically 1-4% of face width - which is what a temporary blemish or
     dust speck looks like, as opposed to pores or larger structures)
  3. inpaint only those specific small regions with cv2.inpaint
  4. blend the inpainted result back at partial opacity

Because the mask only ever covers small isolated spots, pore texture and
skin detail everywhere else is left completely untouched - directly
satisfying the spec's "keep pores, texture, identity" requirement without
needing a trained skin-segmentation model.

NOT implemented (documented gap, needs a trained model to do safely):
  * uneven-skin-tone frequency-separation smoothing over larger areas -
    a blunt blur here risks the "plastic skin" look the spec explicitly
    forbids, so it's left out rather than done poorly
"""

from __future__ import annotations

import cv2
import numpy as np

from ..models import FaceReport

BLEND_OPACITY = 0.7   # < 1.0: leaves a trace of the original for realism


def retouch_portraits(rgb: np.ndarray, faces: FaceReport) -> np.ndarray:
    if not faces.faces:
        return rgb

    out = rgb.copy()
    for face in faces.faces:
        x, y, w, h = face.bbox
        if w < 20 or h < 20:
            continue
        out = _retouch_face_region(out, x, y, w, h)
    return out


def _retouch_face_region(rgb: np.ndarray, x: int, y: int, w: int, h: int) -> np.ndarray:
    region = rgb[y:y + h, x:x + w]
    gray = cv2.cvtColor(region, cv2.COLOR_RGB2GRAY)

    spot_size = max(3, int(round(w * 0.03))) | 1  # odd kernel size
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (spot_size, spot_size))

    tophat = cv2.morphologyEx(gray, cv2.MORPH_TOPHAT, kernel)   # bright spots
    blackhat = cv2.morphologyEx(gray, cv2.MORPH_BLACKHAT, kernel)  # dark spots

    spot_strength = cv2.max(tophat, blackhat)
    _, mask = cv2.threshold(spot_strength, 18, 255, cv2.THRESH_BINARY)
    mask = cv2.dilate(mask, kernel, iterations=1)

    if mask.sum() == 0:
        return rgb

    bgr = cv2.cvtColor(region, cv2.COLOR_RGB2BGR)
    inpainted_bgr = cv2.inpaint(bgr, mask, inpaintRadius=3, flags=cv2.INPAINT_TELEA)
    inpainted = cv2.cvtColor(inpainted_bgr, cv2.COLOR_BGR2RGB)

    mask_f = (mask.astype(np.float32) / 255.0 * BLEND_OPACITY)[:, :, None]
    blended = (region.astype(np.float32) * (1 - mask_f) + inpainted.astype(np.float32) * mask_f)

    result = rgb.copy()
    result[y:y + h, x:x + w] = np.clip(blended, 0, 255).astype(np.uint8)
    return result
