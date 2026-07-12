"""2. STORY DNA ENGINE

Studies successful videos (SHP's own story-dna.json title corpus, scored by
story_score.py, plus SHP's own memory of past productions) and extracts only
STRUCTURE: hook style, pacing, chapter length, reveal timing, curiosity-loop
density, emotional curve shape, ending style. Never reuses their wording.
"""

from __future__ import annotations

from script_agent_v2 import textutil

HOOK_STYLE_BY_TRIGGER = {
    "gizem": "Açılışta çözülmemiş bir sır ilan et, cevabı hemen verme.",
    "catisma": "Açılışta bir çatışma veya tehlike anı göster.",
    "servet": "Açılışta büyük bir kazanç/kayıp riskini göster.",
    "soru": "Açılışı doğrudan cevapsız bırakılan keskin bir soru ile aç.",
    "saskinlik": "Açılışta beklenmedik/şaşırtıcı tek bir görüntü veya iddiayla başla.",
    "vaat": "Açılışta bir cevabın birazdan geleceğine dair açık bir vaat ver.",
}

DEFAULT_TARGET_DURATION_MINUTES = 7


def _select_reference_pool(story_dna: list[dict]) -> list[dict]:
    scored = [row for row in story_dna if isinstance(row.get("story_score"), (int, float))]
    scored.sort(key=lambda row: (row["story_score"], row.get("views_per_day", 0)), reverse=True)
    return scored[:40]


def run(context_dict: dict, story_dna: list[dict], memory: dict) -> dict:
    pool = _select_reference_pool(story_dna)

    trigger_totals: dict[str, int] = {category: 0 for category in textutil.TRIGGER_WORDS}
    for row in pool:
        hits = textutil.trigger_hits(row.get("title", ""))
        for category, matches in hits.items():
            trigger_totals[category] += len(matches)

    dominant_trigger = max(trigger_totals, key=trigger_totals.get) if any(trigger_totals.values()) else "gizem"
    hook_style = HOOK_STYLE_BY_TRIGGER.get(dominant_trigger, HOOK_STYLE_BY_TRIGGER["gizem"])

    video_dna = context_dict.get("video_dna") or {}
    known_duration = video_dna.get("duration_seconds")
    target_seconds = (known_duration or DEFAULT_TARGET_DURATION_MINUTES * 60)
    target_seconds = max(180, min(target_seconds, 900))  # keep in a sane documentary range

    pacing_memory = (memory or {}).get("best_pacing") or {}
    avg_chapter_seconds = pacing_memory.get("avg_chapter_seconds") or 55
    chapter_count = max(6, min(9, round(target_seconds / avg_chapter_seconds)))

    ending_style = (
        "Baştaki soruyu net cevapla, sonra izleyiciyi yeni bir soruyla bırak."
        if dominant_trigger in {"soru", "gizem"}
        else "Duygusal tatmin anıyla kapat ve seriye bağla."
    )

    return {
        "reference_pool_size": len(pool),
        "top_reference_titles": [
            {"title": row.get("title", ""), "story_score": row.get("story_score", 0), "url": row.get("url", "")}
            for row in pool[:5]
        ],
        "dominant_triggers": trigger_totals,
        "recommended_hook_style": hook_style,
        "target_duration_seconds": target_seconds,
        "recommended_chapter_count": chapter_count,
        "recommended_chapter_length_seconds": round(target_seconds / chapter_count),
        "reveal_timing_ratio": 0.7,
        "ending_style": ending_style,
        "curiosity_loop_target_seconds": 25,
        "rule": "Yapı öğrenilir, cümle veya başlık asla kopyalanmaz.",
    }
