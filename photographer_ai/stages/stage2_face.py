"""Stage 2: Face Engine.

Real, classical CV implementation using OpenCV's bundled Haar cascades:
  * face detection             -> haarcascade_frontalface_default
  * eye detection + open/closed -> haarcascade_eye applied within each face
    box; "closed" is inferred when no eye is detected in the expected eye
    region (eyes are one of the highest-contrast features a cascade finds,
    so a miss there is a reasonable, if imperfect, closed-eye signal)
  * facial sharpness           -> Laplacian variance restricted to the face
    bounding box (reuses stage1's sharpness metric on a crop)

Explicitly NOT implemented (need a trained model, listed here so the gap
is documented rather than silently faked):
  * emotion classification
  * smile-quality scoring beyond eye state
  * head pose / gaze direction angle
  * skin-quality / hair-visibility scoring
  * photorealistic eye reconstruction for closed eyes

Per the spec's own principle ("never create fake eyes... only reconstruct
if confidence is high, otherwise mark image for manual review"), eye
restoration is implemented as a pluggable hook (`attempt_eye_restoration`)
that currently always declines and flags for manual review, because doing
this well requires a diffusion/GAN inpainting model we don't have weights
for in this environment. Wiring in a real model later only means
implementing that one function - nothing else in the pipeline changes.
"""

from __future__ import annotations

import cv2
import numpy as np

from ..models import EyeInfo, FaceInfo, FaceReport

_face_cascade = cv2.CascadeClassifier(
    cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
)
_eye_cascade = cv2.CascadeClassifier(
    cv2.data.haarcascades + "haarcascade_eye.xml"
)

EYE_RESTORATION_CONFIDENCE_THRESHOLD = 0.85  # never met by the stub on purpose


def analyze_faces(rgb: np.ndarray) -> FaceReport:
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    detections = _face_cascade.detectMultiScale(
        gray, scaleFactor=1.1, minNeighbors=5, minSize=(40, 40)
    )

    faces = []
    for (x, y, w, h) in detections:
        face_gray = gray[y:y + h, x:x + w]
        face_rgb = rgb[y:y + h, x:x + w]

        facial_sharpness = float(cv2.Laplacian(face_gray, cv2.CV_64F).var())

        left_eye, right_eye = _detect_eyes(face_gray)
        both_open = (not left_eye.is_closed) and (not right_eye.is_closed)

        face = FaceInfo(
            bbox=(int(x), int(y), int(w), int(h)),
            facial_sharpness=facial_sharpness,
            left_eye=left_eye,
            right_eye=right_eye,
            both_eyes_open=both_open,
        )

        if left_eye.is_closed or right_eye.is_closed:
            face = attempt_eye_restoration(face_rgb, face)

        faces.append(face)

    return FaceReport(
        faces=faces,
        face_count=len(faces),
        any_face_needs_review=any(f.needs_manual_review for f in faces),
    )


def _detect_eyes(face_gray: np.ndarray) -> tuple:
    h, w = face_gray.shape
    # Eyes live in the upper half of the face box; restricting the search
    # region cuts down on false positives from nostrils/mouth corners.
    upper_half = face_gray[: h // 2, :]
    eyes = _eye_cascade.detectMultiScale(
        upper_half, scaleFactor=1.1, minNeighbors=6, minSize=(w // 12, w // 12)
    )
    eyes = sorted(eyes, key=lambda e: e[0])  # left-to-right by x

    left_eye = EyeInfo(open_confidence=0.0, is_closed=True)
    right_eye = EyeInfo(open_confidence=0.0, is_closed=True)

    mid_x = w / 2
    for (ex, ey, ew, eh) in eyes:
        info = EyeInfo(open_confidence=0.75, is_closed=False, bbox=(int(ex), int(ey), int(ew), int(eh)))
        if ex + ew / 2 < mid_x:
            left_eye = info
        else:
            right_eye = info

    return left_eye, right_eye


def attempt_eye_restoration(face_rgb: np.ndarray, face: FaceInfo) -> FaceInfo:
    """Hook for closed-eye reconstruction.

    Per spec: never fabricate eyes. This stub always returns low confidence
    and flags for manual review rather than guessing. To plug in a real
    restoration model, replace the body with an inpainting call and only
    set eye_restoration_confidence high when the model itself reports high
    certainty - the threshold check below already gates on that.
    """
    confidence = 0.0  # no model wired in; be honest about it
    face.eye_restoration_attempted = True
    face.eye_restoration_confidence = confidence
    if confidence < EYE_RESTORATION_CONFIDENCE_THRESHOLD:
        face.needs_manual_review = True
    return face
