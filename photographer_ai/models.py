"""Shared data structures passed between pipeline stages."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class Rating(str, Enum):
    HERO = "HERO"
    EXCELLENT = "EXCELLENT"
    GOOD = "GOOD"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    REJECT = "REJECT"


@dataclass
class QualityMetrics:
    sharpness: float = 0.0          # Laplacian variance, higher = sharper
    is_blurry: bool = False
    exposure_mean: float = 0.0      # 0-255 mean luma
    is_overexposed: bool = False
    is_underexposed: bool = False
    clipped_highlights_pct: float = 0.0
    clipped_shadows_pct: float = 0.0
    noise_estimate: float = 0.0
    color_cast_rgb_delta: float = 0.0
    dynamic_range: float = 0.0
    phash: str = ""
    duplicate_of: Optional[str] = None   # filename this image is a near-duplicate of
    burst_group: Optional[int] = None
    quality_score: float = 0.0      # 0-100 aggregate


@dataclass
class EyeInfo:
    open_confidence: float = 0.0   # 0-1, higher = more confident eye is open
    is_closed: bool = False
    bbox: Optional[tuple] = None


@dataclass
class FaceInfo:
    bbox: tuple = (0, 0, 0, 0)     # x, y, w, h in pixels
    facial_sharpness: float = 0.0
    left_eye: EyeInfo = field(default_factory=EyeInfo)
    right_eye: EyeInfo = field(default_factory=EyeInfo)
    both_eyes_open: bool = False
    eye_restoration_attempted: bool = False
    eye_restoration_confidence: float = 0.0
    needs_manual_review: bool = False
    # ML-dependent fields left unset by the classical pipeline; a plugged-in
    # model can populate these (see stages/stage2_face.py docstring).
    emotion: Optional[str] = None
    smile_quality: Optional[float] = None


@dataclass
class FaceReport:
    faces: list = field(default_factory=list)   # list[FaceInfo]
    face_count: int = 0
    any_face_needs_review: bool = False


@dataclass
class CompositionScore:
    rule_of_thirds: float = 0.0
    edge_balance: float = 0.0
    subject_isolation: float = 0.0
    composition_score: float = 0.0   # 0-100 aggregate


@dataclass
class HeroScore:
    hero_score: float = 0.0   # 0-100
    rating: Rating = Rating.NEEDS_REVIEW
    stars: int = 0


@dataclass
class StageStatus:
    """Marks whether a stage ran a real implementation or a documented stub."""
    implemented: bool
    note: str = ""


@dataclass
class ImageRecord:
    """The single object threaded through the whole pipeline for one photo."""
    path: str
    filename: str = ""
    width: int = 0
    height: int = 0

    quality: QualityMetrics = field(default_factory=QualityMetrics)
    faces: FaceReport = field(default_factory=FaceReport)
    composition: CompositionScore = field(default_factory=CompositionScore)
    hero: HeroScore = field(default_factory=HeroScore)

    edited_path: Optional[str] = None
    bw_path: Optional[str] = None
    crop_paths: dict = field(default_factory=dict)     # {"instagram": path, ...}
    export_paths: dict = field(default_factory=dict)   # {"web": path, ...}

    rejected: bool = False
    rejection_reasons: list = field(default_factory=list)

    def __post_init__(self):
        if not self.filename:
            import os
            self.filename = os.path.basename(self.path)
