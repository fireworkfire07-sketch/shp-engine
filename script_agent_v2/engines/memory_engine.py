"""13. MEMORY ENGINE

Remembers SHP's own production history: best hooks, best endings, highest
retention scores, best pacing, best thumbnails. Never replays past wording
verbatim into a new script (that would be self-plagiarism) — it only
extracts aggregate PATTERNS and feeds those forward as lessons.
"""

from __future__ import annotations

import json
from pathlib import Path

MAX_RUNS_KEPT = 25
TOP_N = 5


def hints_for_generation(memory: dict) -> dict:
    """Structure-only lessons handed to the Script Generator prompt."""
    runs = memory.get("runs", []) or []
    approved = [r for r in runs if r.get("approved")]
    if not approved:
        return {"note": "Henüz onaylanmış geçmiş SHP prodüksiyonu yok; ilk video."}

    avg_score = round(sum(r.get("ceo_score", 0) for r in approved) / len(approved))
    hook_lengths = [r.get("hook_word_count", 0) for r in approved if r.get("hook_word_count")]
    return {
        "approved_run_count": len(approved),
        "average_ceo_score": avg_score,
        "average_hook_word_count": round(sum(hook_lengths) / len(hook_lengths)) if hook_lengths else None,
        "best_hook_patterns": [r.get("hook_pattern", "") for r in memory.get("best_hooks", [])[:TOP_N]],
        "best_ending_patterns": [r.get("ending_pattern", "") for r in memory.get("best_endings", [])[:TOP_N]],
        "lesson": "Yapı ve kalıp öğren; hiçbir geçmiş cümleyi birebir tekrar etme.",
    }


def _hook_pattern(hook: str) -> str:
    word_count = len(hook.split())
    has_question = "?" in hook
    return f"{word_count} kelime, {'soru formunda' if has_question else 'iddia formunda'}"


def _ending_pattern(sections: list[dict]) -> str:
    if not sections:
        return ""
    last = str(sections[-1].get("voiceover", ""))
    return f"{len(last.split())} kelime, {'soru ile kapanış' if '?' in last else 'ifade ile kapanış'}"


def record(memory: dict, script: dict, ceo_review: dict, evaluations: dict, story_dna_plan: dict) -> dict:
    hook = str(script.get("hook", ""))
    entry = {
        "generated_at": ceo_review.get("reviewed_at", ""),
        "title": script.get("title", ""),
        "hook_pattern": _hook_pattern(hook),
        "hook_word_count": len(hook.split()),
        "ending_pattern": _ending_pattern(script.get("sections", [])),
        "ceo_score": ceo_review.get("ceo_score", 0),
        "curiosity_score": evaluations.get("curiosity", {}).get("overall_score", 0),
        "retention_score": evaluations.get("retention", {}).get("overall_score", 0),
        "chapter_count": len(script.get("sections", [])),
        "avg_chapter_seconds": story_dna_plan.get("recommended_chapter_length_seconds", 0),
        "thumbnail_concept": script.get("thumbnail_concept", ""),
        "approved": ceo_review.get("decision") == "APPROVE",
    }

    runs = memory.get("runs", []) or []
    runs.append(entry)
    runs = runs[-MAX_RUNS_KEPT:]

    approved = [r for r in runs if r.get("approved")]
    best_hooks = sorted(approved, key=lambda r: r.get("ceo_score", 0), reverse=True)[:TOP_N]
    best_endings = sorted(approved, key=lambda r: r.get("retention_score", 0), reverse=True)[:TOP_N]
    best_thumbnails = sorted(approved, key=lambda r: r.get("ceo_score", 0), reverse=True)[:TOP_N]

    avg_chapter_seconds = (
        round(sum(r.get("avg_chapter_seconds", 0) for r in approved) / len(approved)) if approved else None
    )

    memory = {
        "runs": runs,
        "best_hooks": [{"hook_pattern": r["hook_pattern"], "ceo_score": r["ceo_score"]} for r in best_hooks],
        "best_endings": [{"ending_pattern": r["ending_pattern"], "retention_score": r["retention_score"]} for r in best_endings],
        "best_thumbnails": [{"thumbnail_concept": r["thumbnail_concept"], "ceo_score": r["ceo_score"]} for r in best_thumbnails],
        "best_pacing": {"avg_chapter_seconds": avg_chapter_seconds} if avg_chapter_seconds else {},
    }
    return memory


def save(memory: dict, path: Path) -> None:
    path.write_text(json.dumps(memory, ensure_ascii=False, indent=2), encoding="utf-8")
