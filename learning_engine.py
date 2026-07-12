"""SHP Learning Engine — learns real structural patterns from SHP's own
channel performance, production history and decisions, and feeds them
forward into Niche Intelligence, Script Agent V2 and Video CEO Pro.

Never invents analytics: this system has no YouTube Analytics OAuth
connection anywhere (only the public YouTube Data API v3), so CTR, average
view duration and retention are always explicitly marked unavailable
rather than estimated or guessed.

Never stores or reuses competitor wording: only title/hook STRUCTURE is
learned (trigger-word categories, length, question-form), the same
discipline script_agent_v2/engines/memory_engine.py already applies to
SHP's own scripts — this module applies it to real published-video
performance data too.

Maintains its own persisted run history across workflow runs (like
memory_engine.py does for Script Agent V2) — a single run's snapshot
cannot teach a trend by itself.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from story_score import score_title

ROOT = Path("projects")
OUTPUT_DIR = ROOT / "learning-engine"
MEMORY_PATH = OUTPUT_DIR / "memory.json"
MAX_RUNS_KEPT = 50

TRIGGER_CATEGORIES = ["gizem", "catismа", "servet", "soru", "saskinlik"]


def load_json(path: Path, default=None):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def load_memory() -> dict:
    return load_json(MEMORY_PATH, {"runs": [], "trigger_category_performance": {}}) or {
        "runs": [], "trigger_category_performance": {},
    }


def save_memory(memory: dict) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    MEMORY_PATH.write_text(json.dumps(memory, ensure_ascii=False, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# Real, structural lessons only — never verbatim wording.
# ---------------------------------------------------------------------------

def analyze_title_patterns(own_videos: list[dict]) -> dict:
    """Correlates SHP's own published video titles' trigger-word categories
    (structure) against real views_per_day. Never stores or reuses the
    titles themselves — only the category -> average-performance mapping."""
    public = [v for v in own_videos if v.get("privacy_status", "public") == "public" and v.get("views_per_day")]
    if not public:
        return {"available": False, "reason": "Herkese açık video verisi yok.", "by_category": {}}

    totals: dict[str, list[float]] = {cat: [] for cat in TRIGGER_CATEGORIES}
    for video in public:
        title = str(video.get("title", ""))
        speed = float(video.get("views_per_day", 0) or 0)
        hits = score_title(title)["trigger_hits"]
        for category in TRIGGER_CATEGORIES:
            if hits.get(category):
                totals[category].append(speed)

    by_category = {}
    for category, speeds in totals.items():
        if speeds:
            by_category[category] = {
                "video_count": len(speeds),
                "average_views_per_day": round(sum(speeds) / len(speeds), 1),
            }

    overall_avg = sum(float(v.get("views_per_day", 0) or 0) for v in public) / len(public)
    best_category = max(by_category, key=lambda c: by_category[c]["average_views_per_day"]) if by_category else None

    return {
        "available": True,
        "videos_analyzed": len(public),
        "overall_average_views_per_day": round(overall_avg, 1),
        "by_category": by_category,
        "best_performing_category": best_category,
    }


def analyze_production_funnel(script_memory: dict, video_ceo: dict, video_engine: dict) -> dict:
    """Approved/rejected scripts, Video CEO decisions, production results —
    real counts from what actually happened, not estimates."""
    runs = script_memory.get("runs", []) if script_memory else []
    approved = [r for r in runs if r.get("approved")]
    return {
        "script_agent_runs_recorded": len(runs),
        "script_agent_approval_rate": round(len(approved) / len(runs), 2) if runs else None,
        "latest_video_ceo_decision": video_ceo.get("decision") if video_ceo else None,
        "latest_video_ceo_score": video_ceo.get("video_ceo_score") if video_ceo else None,
        "latest_video_engine_status": video_engine.get("status") if video_engine else None,
    }


def analytics_availability() -> dict:
    """This system only ever uses the public YouTube Data API v3 — there is
    no OAuth connection to YouTube Analytics anywhere in the codebase, so
    these must always be reported as unavailable rather than guessed."""
    return {
        "ctr": "kullanılamıyor (YouTube Analytics OAuth bağlı değil)",
        "average_view_duration": "kullanılamıyor (YouTube Analytics OAuth bağlı değil)",
        "audience_retention": "kullanılamıyor (YouTube Analytics OAuth bağlı değil)",
    }


def update_trigger_category_performance(memory: dict, title_patterns: dict) -> dict:
    history = memory.get("trigger_category_performance", {})
    if title_patterns.get("available"):
        for category, stats in title_patterns.get("by_category", {}).items():
            history.setdefault(category, []).append(stats["average_views_per_day"])
            history[category] = history[category][-MAX_RUNS_KEPT:]
    return history


def build_lessons(title_patterns: dict, funnel: dict, trigger_history: dict) -> dict:
    trend_by_category = {}
    for category, values in trigger_history.items():
        if len(values) >= 2:
            trend_by_category[category] = "yükseliyor" if values[-1] >= values[0] else "düşüyor"

    return {
        "best_title_trigger_category": title_patterns.get("best_performing_category"),
        "trigger_category_trend": trend_by_category,
        "script_agent_approval_rate": funnel.get("script_agent_approval_rate"),
        "note": "Yapı öğrenilir (tetikleyici kategori, uzunluk, soru biçimi); hiçbir başlık veya cümle birebir saklanmaz veya tekrar kullanılmaz.",
    }


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    channel = load_json(ROOT / "channel-health" / "analysis.json", {}) or {}
    script_memory = load_json(ROOT / "script-agent" / "memory.json", {}) or {}
    video_ceo = load_json(ROOT / "video-ceo" / "analysis.json", {}) or {}
    video_engine = load_json(ROOT / "video-engine" / "render_manifest.json", {}) or {}

    own_videos = (channel.get("top_videos", []) or []) + (channel.get("bottom_videos", []) or [])
    title_patterns = analyze_title_patterns(own_videos)
    funnel = analyze_production_funnel(script_memory, video_ceo, video_engine)
    analytics = analytics_availability()

    memory = load_memory()
    trigger_history = update_trigger_category_performance(memory, title_patterns)
    lessons = build_lessons(title_patterns, funnel, trigger_history)

    run_entry = {
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "title_patterns": title_patterns,
        "funnel": funnel,
    }
    runs = memory.get("runs", [])
    runs.append(run_entry)
    runs = runs[-MAX_RUNS_KEPT:]

    memory = {
        "runs": runs,
        "trigger_category_performance": trigger_history,
        "lessons": lessons,
        "analytics_availability": analytics,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    save_memory(memory)

    report_lines = [
        "# SHP Learning Engine Raporu", "",
        f"**Analiz edilen video sayısı:** {title_patterns.get('videos_analyzed', 0)}",
        f"**En güçlü başlık tetikleyici kategorisi:** {lessons.get('best_title_trigger_category') or 'yeterli veri yok'}",
        f"**Script Agent onay oranı:** {funnel.get('script_agent_approval_rate')}",
        f"**Son Video CEO kararı:** {funnel.get('latest_video_ceo_decision')} ({funnel.get('latest_video_ceo_score')}/100)",
        f"**Son Video Engine durumu:** {funnel.get('latest_video_engine_status')}",
        "",
        "## Başlık tetikleyici kategorisi performansı", "",
    ]
    if title_patterns.get("available"):
        report_lines += ["| Kategori | Video sayısı | Ortalama günlük izlenme |", "|---|---:|---:|"]
        for category, stats in title_patterns.get("by_category", {}).items():
            report_lines.append(f"| {category} | {stats['video_count']} | {stats['average_views_per_day']} |")
    else:
        report_lines.append(f"- {title_patterns.get('reason', 'Veri yok.')}")

    report_lines += [
        "", "## YouTube Analytics kullanılabilirliği", "",
        f"- CTR: {analytics['ctr']}",
        f"- Ortalama izlenme süresi: {analytics['average_view_duration']}",
        f"- İzleyici tutma: {analytics['audience_retention']}",
        "", "## Gerçek sınırlar", "",
        "- Bu modül yalnızca yapısal dersler saklar (tetikleyici kategori, onay oranı, üretim sonucu); hiçbir başlık, cümle veya rakip metni birebir saklamaz ya da yeniden kullanmaz.",
        "- YouTube Analytics OAuth bağlantısı yok; CTR/izlenme süresi/tutma asla tahmin edilmez, her zaman 'kullanılamıyor' olarak işaretlenir.",
        "- Dersler Niche Intelligence, Script Agent V2 ve Video CEO Pro'ya sonraki çalıştırmalarda beslenir.",
    ]
    (OUTPUT_DIR / "report.md").write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    print(f"LEARNING_BEST_CATEGORY={lessons.get('best_title_trigger_category')}")
    print(f"LEARNING_APPROVAL_RATE={funnel.get('script_agent_approval_rate')}")


if __name__ == "__main__":
    main()
