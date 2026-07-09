from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
import json

from .config import Settings, get_settings


@dataclass
class VideoJob:
    """A single video production job."""

    topic: str
    title: str | None = None
    language: str = "tr"
    privacy_status: str = "private"


@dataclass
class PipelineResult:
    """Result written after each dry-run or production run."""

    status: str
    job: VideoJob
    output_path: str
    created_at: str
    next_steps: list[str]


def build_job(topic: str, settings: Settings | None = None) -> VideoJob:
    settings = settings or get_settings()
    clean_topic = topic.strip()
    if not clean_topic:
        raise ValueError("Topic cannot be empty.")

    return VideoJob(
        topic=clean_topic,
        title=f"The Secret History of {clean_topic}",
        privacy_status=settings.youtube_privacy_status,
    )


def run_pipeline(topic: str, settings: Settings | None = None) -> PipelineResult:
    """Run the first safe pipeline pass.

    This version intentionally performs a dry-run only. It creates a job manifest
    and keeps YouTube privacy set to private so the system can be tested safely.
    """

    settings = settings or get_settings()
    output_dir = settings.ensure_output_dir()
    job = build_job(topic, settings)

    created_at = datetime.now(timezone.utc).isoformat()
    manifest_path = output_dir / "latest_job.json"

    result = PipelineResult(
        status="dry_run_created",
        job=job,
        output_path=str(manifest_path),
        created_at=created_at,
        next_steps=[
            "Connect script generator agent",
            "Connect voiceover agent",
            "Connect image/video scene generator",
            "Connect YouTube uploader with privacyStatus=private",
        ],
    )

    manifest_path.write_text(json.dumps(asdict(result), indent=2, ensure_ascii=False), encoding="utf-8")
    return result
