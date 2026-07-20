from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
import json
import re

from .config import Settings, get_settings
from .content import create_scenes
from .renderer import render_video


@dataclass
class VideoJob:
    topic: str
    title: str
    language: str = "tr"
    privacy_status: str = "private"


@dataclass
class PipelineResult:
    status: str
    job: VideoJob
    video_path: str
    manifest_path: str
    created_at: str
    scene_count: int


def _slugify(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9ğüşöçıİĞÜŞÖÇ]+", "-", value, flags=re.IGNORECASE)
    return value.strip("-") or "video"


def build_job(topic: str, settings: Settings | None = None) -> VideoJob:
    settings = settings or get_settings()
    clean_topic = topic.strip()
    if not clean_topic:
        raise ValueError("Topic cannot be empty.")
    return VideoJob(
        topic=clean_topic,
        title=f"{clean_topic}: Gizli Hikâye",
        privacy_status=settings.youtube_privacy_status,
    )


def run_pipeline(topic: str, settings: Settings | None = None) -> PipelineResult:
    """Create scenes, render a real MP4, and save a machine-readable manifest."""
    settings = settings or get_settings()
    output_dir = settings.ensure_output_dir()
    job = build_job(topic, settings)
    scenes = create_scenes(job.topic)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    job_dir = output_dir / f"{timestamp}-{_slugify(job.topic)}"
    job_dir.mkdir(parents=True, exist_ok=True)

    video_path = render_video(scenes, job_dir / "video.mp4")
    manifest_path = job_dir / "manifest.json"
    result = PipelineResult(
        status="video_created",
        job=job,
        video_path=str(video_path),
        manifest_path=str(manifest_path),
        created_at=datetime.now(timezone.utc).isoformat(),
        scene_count=len(scenes),
    )
    manifest_path.write_text(json.dumps(asdict(result), indent=2, ensure_ascii=False), encoding="utf-8")
    return result
