"""Stage 4: Composition Engine.

Real heuristic implementation built on classical image-processing signals -
there is no trained aesthetic-scoring model here, but the three sub-scores
below are each a legitimate, independently-computed measurement:

  * rule_of_thirds     -> distance from the frame's dominant "subject point"
                           (a detected face center, falling back to the
                           center of visual mass from a Sobel energy map) to
                           the nearest rule-of-thirds intersection
  * edge_balance        -> how evenly visual weight (gradient energy) is
                           distributed across the 3x3 thirds grid; used as a
                           proxy for leading-lines / framing / negative-space
                           quality, since all of those manifest as energy
                           spread rather than one dead-center blob
  * subject_isolation   -> sharpness of the subject region vs. the
                           background (bokeh / depth-of-field proxy)

Golden-ratio scoring, explicit leading-line detection (Hough-line based),
and true saliency (which needs a trained model to match human attention
well) are documented gaps - rule_of_thirds already approximates a chunk of
what golden-ratio scoring would add, and a Hough-line leading-lines score
can be added as a fourth sub-score without touching the rest of the stage.
"""

from __future__ import annotations

import cv2
import numpy as np

from ..models import CompositionScore, FaceReport

THIRDS_FRACTIONS = (1 / 3, 2 / 3)


def analyze_composition(rgb: np.ndarray, faces: FaceReport) -> CompositionScore:
    h, w = rgb.shape[:2]
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    energy = _energy_map(gray)

    subject_point = _subject_point(faces, energy, w, h)
    rule_of_thirds = _rule_of_thirds_score(subject_point, w, h)
    edge_balance = _edge_balance_score(energy)
    subject_isolation = _subject_isolation_score(gray, faces, energy)

    composition_score = float(
        0.4 * rule_of_thirds + 0.3 * edge_balance + 0.3 * subject_isolation
    )

    return CompositionScore(
        rule_of_thirds=rule_of_thirds,
        edge_balance=edge_balance,
        subject_isolation=subject_isolation,
        composition_score=composition_score,
    )


def _energy_map(gray: np.ndarray) -> np.ndarray:
    gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    return cv2.magnitude(gx, gy)


def _subject_point(faces: FaceReport, energy: np.ndarray, w: int, h: int) -> tuple:
    if faces.faces:
        largest = max(faces.faces, key=lambda f: f.bbox[2] * f.bbox[3])
        x, y, fw, fh = largest.bbox
        return (x + fw / 2, y + fh / 2)

    # No face: use the centroid of visual energy as a saliency proxy.
    total = energy.sum()
    if total <= 0:
        return (w / 2, h / 2)
    ys, xs = np.indices(energy.shape)
    cx = float((xs * energy).sum() / total)
    cy = float((ys * energy).sum() / total)
    return (cx, cy)


def _rule_of_thirds_score(point: tuple, w: int, h: int) -> float:
    px, py = point
    intersections = [
        (fx * w, fy * h) for fx in THIRDS_FRACTIONS for fy in THIRDS_FRACTIONS
    ]
    dists = [np.hypot(px - ix, py - iy) for ix, iy in intersections]
    min_dist = min(dists)
    diagonal = np.hypot(w, h)
    normalized = min_dist / diagonal  # 0 = right on an intersection
    return float(max(0.0, 100.0 * (1.0 - normalized * 2.5)))


def _edge_balance_score(energy: np.ndarray) -> float:
    h, w = energy.shape
    ys = [0, h // 3, 2 * h // 3, h]
    xs = [0, w // 3, 2 * w // 3, w]
    cell_sums = []
    for i in range(3):
        for j in range(3):
            cell = energy[ys[i]:ys[i + 1], xs[j]:xs[j + 1]]
            cell_sums.append(float(cell.mean()) if cell.size else 0.0)

    cell_sums = np.array(cell_sums)
    if cell_sums.sum() <= 0:
        return 50.0

    # Reward compositions where energy is spread across multiple cells
    # (leading lines / layered depth) rather than concentrated in one flat
    # blob or perfectly uniform (which usually means "boring/no subject").
    normalized = cell_sums / cell_sums.sum()
    entropy = -np.sum(normalized * np.log(normalized + 1e-9))
    max_entropy = np.log(len(cell_sums))
    return float(100.0 * (entropy / max_entropy))


def _subject_isolation_score(gray: np.ndarray, faces: FaceReport, energy: np.ndarray) -> float:
    h, w = gray.shape
    mask = np.zeros((h, w), dtype=bool)

    if faces.faces:
        for f in faces.faces:
            x, y, fw, fh = f.bbox
            mask[y:y + fh, x:x + fw] = True
    else:
        # No face: treat the highest-energy quartile of pixels as "subject".
        threshold = np.percentile(energy, 75)
        mask = energy >= threshold

    if mask.sum() == 0 or (~mask).sum() == 0:
        return 50.0

    lap = cv2.Laplacian(gray, cv2.CV_64F)
    subject_var = float(lap[mask].var())
    background_var = float(lap[~mask].var())

    if background_var <= 1e-6:
        ratio = 1.0
    else:
        ratio = subject_var / background_var

    # ratio > 1 means subject sharper than background (good isolation).
    return float(max(0.0, min(100.0, 50.0 + 15.0 * np.log(max(ratio, 1e-3)))))
