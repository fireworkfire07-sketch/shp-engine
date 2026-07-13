"""Stage 3: Body Analysis.

Real implementation using MediaPipe's BlazePose landmarker (33 body
keypoints with per-keypoint visibility/presence scores), lazily downloaded
and cached on first use. From those real landmarks we compute:

  * leaning posture / body tilt -> shoulder-line and hip-line angle vs.
    horizontal
  * body symmetry               -> left/right shoulder & hip height
    difference
  * cropped limbs                -> wrist/ankle landmarks with low
    visibility or that fall within a few percent of the frame edge
  * pose_quality_score            -> 0-100 aggregate of the above

This needs network access on first run to fetch the ~6MB model file from
Google's public MediaPipe model store, and the `libgles2`/`libegl1`
system libraries MediaPipe's native runtime links against. Both are
optional: if either is unavailable, `analyze_body` degrades gracefully to
an unimplemented BodyReport (`implemented=False`) instead of crashing the
batch, so this stage works as "real when available, honestly absent when
not" rather than ever faking a result.

NOT implemented (documented gaps needing more than pose keypoints):
  * finger-level visibility / cut-finger detection - needs the separate
    hand-landmarker model, not wired in here (same lazy-load pattern would
    apply)
  * semantic "awkward pose" / "natural stance" judgment - pose_quality_score
    is a geometric proxy, not a learned aesthetic judgment
  * hidden-face-behind-body detection - would cross-reference Stage 2's
    face boxes against body landmark positions, not yet wired
"""

from __future__ import annotations

import os
import urllib.request
from dataclasses import dataclass, field

import numpy as np

MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/pose_landmarker/"
    "pose_landmarker_lite/float16/latest/pose_landmarker_lite.task"
)
MODEL_CACHE_PATH = os.path.expanduser(
    "~/.cache/photographer_ai/models/pose_landmarker_lite.task"
)
EDGE_MARGIN_FRACTION = 0.02   # within 2% of frame edge counts as "cropped"
VISIBILITY_THRESHOLD = 0.5

# Landmark indices per MediaPipe's 33-point pose topology.
_LEFT_SHOULDER, _RIGHT_SHOULDER = 11, 12
_LEFT_HIP, _RIGHT_HIP = 23, 24
_LEFT_WRIST, _RIGHT_WRIST = 15, 16
_LEFT_ANKLE, _RIGHT_ANKLE = 27, 28

_landmarker = None
_load_failed = False


@dataclass
class BodyInfo:
    shoulder_tilt_deg: float = 0.0
    hip_tilt_deg: float = 0.0
    symmetry_score: float = 0.0       # 0-100, 100 = perfectly level
    cropped_landmarks: list = field(default_factory=list)  # e.g. ["left_wrist"]
    pose_quality_score: float = 0.0


@dataclass
class BodyReport:
    implemented: bool
    people: list = field(default_factory=list)   # list[BodyInfo]
    note: str = ""


def _get_landmarker():
    global _landmarker, _load_failed
    if _landmarker is not None or _load_failed:
        return _landmarker
    try:
        import mediapipe as mp
        from mediapipe.tasks import python as mp_python
        from mediapipe.tasks.python import vision

        os.makedirs(os.path.dirname(MODEL_CACHE_PATH), exist_ok=True)
        if not os.path.exists(MODEL_CACHE_PATH):
            urllib.request.urlretrieve(MODEL_URL, MODEL_CACHE_PATH)

        base_options = mp_python.BaseOptions(model_asset_path=MODEL_CACHE_PATH)
        options = vision.PoseLandmarkerOptions(
            base_options=base_options,
            num_poses=5,
            output_segmentation_masks=False,
        )
        _landmarker = vision.PoseLandmarker.create_from_options(options)
    except Exception as exc:  # noqa: BLE001 - any failure => documented degrade
        _load_failed = True
        _landmarker = None
        _load_failure_reason = str(exc)
        globals()["_load_failure_reason"] = _load_failure_reason
    return _landmarker


def analyze_body(rgb: np.ndarray) -> BodyReport:
    landmarker = _get_landmarker()
    if landmarker is None:
        return BodyReport(
            implemented=False,
            note=(
                "Pose model unavailable (no network on first run to fetch "
                "the model, or missing libgles2/libegl1 system libraries). "
                f"Detail: {globals().get('_load_failure_reason', 'unknown')}"
            ),
        )

    import mediapipe as mp

    h, w = rgb.shape[:2]
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
    result = landmarker.detect(mp_image)

    people = [_analyze_pose(lm, w, h) for lm in result.pose_landmarks]
    return BodyReport(implemented=True, people=people)


def _analyze_pose(landmarks, w: int, h: int) -> BodyInfo:
    pts = [(lm.x * w, lm.y * h, lm.visibility) for lm in landmarks]

    shoulder_tilt = _angle_deg(pts[_LEFT_SHOULDER], pts[_RIGHT_SHOULDER])
    hip_tilt = _angle_deg(pts[_LEFT_HIP], pts[_RIGHT_HIP])
    symmetry_score = max(0.0, 100.0 - (abs(shoulder_tilt) + abs(hip_tilt)) * 4.0)

    cropped = []
    for idx, name in (
        (_LEFT_WRIST, "left_wrist"), (_RIGHT_WRIST, "right_wrist"),
        (_LEFT_ANKLE, "left_ankle"), (_RIGHT_ANKLE, "right_ankle"),
    ):
        x, y, vis = pts[idx]
        near_edge = (
            x < w * EDGE_MARGIN_FRACTION or x > w * (1 - EDGE_MARGIN_FRACTION)
            or y < h * EDGE_MARGIN_FRACTION or y > h * (1 - EDGE_MARGIN_FRACTION)
        )
        if vis < VISIBILITY_THRESHOLD or near_edge:
            cropped.append(name)

    pose_quality = symmetry_score - 10.0 * len(cropped)
    pose_quality = float(max(0.0, min(100.0, pose_quality)))

    return BodyInfo(
        shoulder_tilt_deg=shoulder_tilt,
        hip_tilt_deg=hip_tilt,
        symmetry_score=symmetry_score,
        cropped_landmarks=cropped,
        pose_quality_score=pose_quality,
    )


def _angle_deg(p1: tuple, p2: tuple) -> float:
    dx = p2[0] - p1[0]
    dy = p2[1] - p1[1]
    return float(np.degrees(np.arctan2(dy, dx)))
