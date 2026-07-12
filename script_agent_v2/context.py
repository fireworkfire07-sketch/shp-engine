"""Gathers everything upstream SHP agents already know before Script Agent V2
writes a single word. No engine re-fetches YouTube or SHP data on its own —
it all flows through this single ProductionContext.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path("projects")
OUTPUT_DIR = ROOT / "script-agent"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
MEMORY_PATH = OUTPUT_DIR / "memory.json"
LEARNING_ENGINE_MEMORY_PATH = ROOT / "learning-engine" / "memory.json"


def load_json(path: Path, default=None):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def latest_video_dna() -> dict:
    root = ROOT / "video-dna"
    if not root.exists():
        return {}
    candidates = sorted(root.glob("*/analysis.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    return load_json(candidates[0], {}) if candidates else {}


@dataclass
class ProductionContext:
    topic: str
    niche: str
    decision: str
    effort_verdict: str
    first_3_seconds: str
    retention_plan: list
    engagement_plan: list
    keywords: list
    hashtags: list
    competitor_reference: dict
    video_dna: dict
    channel: dict
    competitors: dict
    story_dna: list
    memory: dict
    thumbnail_direction: str
    hook_direction: str
    channel_lessons: dict

    def as_dict(self) -> dict:
        return {
            "topic": self.topic,
            "niche": self.niche,
            "decision": self.decision,
            "effort_verdict": self.effort_verdict,
            "first_3_seconds": self.first_3_seconds,
            "retention_plan": self.retention_plan,
            "engagement_plan": self.engagement_plan,
            "keywords": self.keywords,
            "hashtags": self.hashtags,
            "competitor_reference": self.competitor_reference,
            "video_dna": self.video_dna,
            "thumbnail_direction": self.thumbnail_direction,
            "hook_direction": self.hook_direction,
            "channel_lessons": self.channel_lessons,
        }


def build_context() -> ProductionContext:
    ceo = load_json(ROOT / "ceo-decision" / "analysis.json", {})
    growth = load_json(ROOT / "growth-advisor" / "analysis.json", {})
    niche = load_json(ROOT / "niche-intelligence" / "analysis.json", {})
    channel = load_json(ROOT / "channel-health" / "analysis.json", {})
    competitors = load_json(ROOT / "competitor-health" / "analysis.json", {})
    story_dna = load_json(ROOT / "story-dna.json", [])
    memory = load_json(MEMORY_PATH, {"runs": [], "best_hooks": [], "best_endings": [], "best_thumbnails": []})
    learning = load_json(LEARNING_ENGINE_MEMORY_PATH, {}) or {}
    channel_lessons = learning.get("lessons", {}) or {}

    winner = (niche or {}).get("winner", {}) or {}

    return ProductionContext(
        topic=ceo.get("video_idea") or winner.get("first_10_video_ideas", [""])[0] or winner.get("niche", ""),
        niche=winner.get("niche") or ceo.get("topic", ""),
        decision=ceo.get("decision", ""),
        effort_verdict=ceo.get("effort_verdict", ""),
        first_3_seconds=growth.get("first_3_seconds", ""),
        retention_plan=growth.get("retention_plan", []) or [],
        engagement_plan=growth.get("engagement_plan", []) or [],
        keywords=growth.get("trending_keywords", []) or [],
        hashtags=growth.get("hashtags", []) or [],
        competitor_reference=ceo.get("competitor_reference", {}) or {},
        video_dna=latest_video_dna(),
        channel=channel or {},
        competitors=competitors or {},
        story_dna=story_dna if isinstance(story_dna, list) else [],
        memory=memory if isinstance(memory, dict) else {"runs": [], "best_hooks": [], "best_endings": [], "best_thumbnails": []},
        thumbnail_direction=ceo.get("thumbnail_direction", ""),
        hook_direction=ceo.get("hook_direction", ""),
        channel_lessons=channel_lessons,
    )
