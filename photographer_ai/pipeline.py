"""End-to-end orchestrator: ingest -> analyze -> score -> edit -> export.

Each stage is a pure function on one image (see stages/), so this module's
only job is sequencing them and carrying state in ImageRecord. Stages are
called one image at a time rather than in parallel; every stage function
here is independent per-image, so wrapping this loop in
`concurrent.futures.ProcessPoolExecutor` is the natural next step for
batch throughput and doesn't require touching any stage - documented here
rather than done, since correctness came first for this pass.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field

from . import io_utils
from .models import ImageRecord, Rating
from .stages import (
    stage1_quality,
    stage2_face,
    stage3_body,
    stage4_composition,
    stage5_background,
    stage6_lightroom,
    stage7_crop,
    stage8_retouch,
    stage9_hero,
    stage10_bw,
    stage11_shadow,
    stage12_export,
)


@dataclass
class PipelineConfig:
    output_dir: str = "photographer_ai_output"
    enable_body_analysis: bool = True
    enable_background_cleanup: bool = True
    enable_retouch: bool = True
    enable_cinematic_shadow: bool = True
    bw_hero_only: bool = True
    hero_ratings_for_bw: tuple = (Rating.HERO, Rating.EXCELLENT)
    on_progress: "callable | None" = None


@dataclass
class BatchResult:
    records: list = field(default_factory=list)   # list[ImageRecord]
    buckets: dict = field(default_factory=dict)
    elapsed_seconds: float = 0.0


def run_batch(input_dir: str, config: PipelineConfig) -> BatchResult:
    start = time.time()
    paths = io_utils.list_images(input_dir)
    records = [ImageRecord(path=p) for p in paths]

    _report(config, f"Found {len(records)} images")

    rgb_cache = {}
    for i, record in enumerate(records):
        rgb = io_utils.load_rgb(record.path)
        rgb_cache[record.filename] = rgb
        record.height, record.width = rgb.shape[:2]
        record.quality = stage1_quality.analyze_quality(rgb)
        _report(config, f"[{i + 1}/{len(records)}] quality analyzed: {record.filename}")

    stage1_quality.detect_duplicates_and_bursts(records)

    for i, record in enumerate(records):
        rgb = rgb_cache[record.filename]

        record.faces = stage2_face.analyze_faces(rgb)

        if config.enable_background_cleanup:
            rgb, bg_report = stage5_background.clean_background(rgb, record.faces)
            rgb_cache[record.filename] = rgb
        else:
            bg_report = None

        record.composition = stage4_composition.analyze_composition(rgb, record.faces)

        if config.enable_body_analysis:
            body_report = stage3_body.analyze_body(rgb)
        else:
            body_report = None

        record.hero = stage9_hero.score_hero(record.quality, record.faces, record.composition)

        if record.hero.rating == Rating.REJECT or record.quality.duplicate_of is not None:
            record.rejected = True
            if record.hero.rating == Rating.REJECT:
                record.rejection_reasons.append("low hero score")
            if record.quality.duplicate_of is not None:
                record.rejection_reasons.append(f"near-duplicate of {record.quality.duplicate_of}")

        _report(config, f"[{i + 1}/{len(records)}] scored: {record.filename} -> {record.hero.rating.value} ({record.hero.stars}★)")

        setattr(record, "_body_report", body_report)
        setattr(record, "_background_report", bg_report)

    buckets = stage9_hero.rank_batch(records)

    for i, record in enumerate(records):
        if record.rejected:
            continue
        rgb = rgb_cache[record.filename]

        edited = stage6_lightroom.auto_edit(rgb, record.quality)

        if config.enable_retouch:
            edited = stage8_retouch.retouch_portraits(edited, record.faces)

        subject_point = _subject_point(record)
        if config.enable_cinematic_shadow:
            edited = stage11_shadow.apply_cinematic_shadow(edited, subject_point)

        is_hero = record.hero.rating in config.hero_ratings_for_bw
        bw = stage10_bw.convert_bw(edited) if (is_hero or not config.bw_hero_only) else None

        crops = stage7_crop.generate_crops(edited, record.faces, subject_point)

        stem = os.path.splitext(record.filename)[0]
        record.export_paths = stage12_export.export_all(
            stem, config.output_dir, edited, bw, crops, is_hero
        )
        record.edited_path = record.export_paths.get("high_resolution")
        record.bw_path = record.export_paths.get("black_white_hero")

        _report(config, f"[{i + 1}/{len(records)}] exported: {record.filename}")

    _write_report(records, buckets, config.output_dir)

    return BatchResult(records=records, buckets=buckets, elapsed_seconds=time.time() - start)


def _subject_point(record: ImageRecord) -> tuple:
    if record.faces.faces:
        f = max(record.faces.faces, key=lambda f: f.bbox[2] * f.bbox[3])
        x, y, w, h = f.bbox
        return (x + w / 2, y + h / 2)
    return (record.width / 2, record.height / 2)


def _report(config: PipelineConfig, message: str) -> None:
    if config.on_progress:
        config.on_progress(message)


def _write_report(records: list, buckets: dict, output_dir: str) -> None:
    os.makedirs(output_dir, exist_ok=True)
    summary = {
        "total": len(records),
        "rejected": sum(1 for r in records if r.rejected),
        "by_stars": {str(stars): len(items) for stars, items in buckets.items()},
        "images": [
            {
                "filename": r.filename,
                "stars": r.hero.stars,
                "rating": r.hero.rating.value,
                "hero_score": round(r.hero.hero_score, 1),
                "quality_score": round(r.quality.quality_score, 1),
                "composition_score": round(r.composition.composition_score, 1),
                "face_count": r.faces.face_count,
                "rejected": r.rejected,
                "rejection_reasons": r.rejection_reasons,
                "duplicate_of": r.quality.duplicate_of,
                "edited_path": r.edited_path,
                "export_paths": r.export_paths,
            }
            for r in records
        ],
    }
    with open(os.path.join(output_dir, "report.json"), "w") as f:
        json.dump(summary, f, indent=2)
