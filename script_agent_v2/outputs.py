"""Writes the 9 deliverables Script Agent V2 hands off: script.md, script.json,
storyboard.json, visual_prompts.json, voiceover.txt, subtitle.srt,
thumbnail.json, youtube_upload.json, video_engine_handoff.json.
"""

from __future__ import annotations

import json
from pathlib import Path

from script_agent_v2 import textutil
from script_agent_v2.context import OUTPUT_DIR


def _seconds_to_srt_timestamp(seconds: float) -> str:
    seconds = max(0.0, seconds)
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int(round((seconds - int(seconds)) * 1000))
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def build_subtitle_srt(sections: list[dict]) -> str:
    cues = []
    elapsed = 0.0
    index = 1
    for section in sections:
        for sentence in textutil.split_sentences(str(section.get("voiceover", ""))):
            duration = max(1.2, textutil.estimate_seconds(sentence))
            start, end = elapsed, elapsed + duration
            cues.append(f"{index}\n{_seconds_to_srt_timestamp(start)} --> {_seconds_to_srt_timestamp(end)}\n{sentence}\n")
            elapsed = end
            index += 1
    return "\n".join(cues)


def build_voiceover_txt(script: dict) -> str:
    lines = [f"[Hook]\n{script.get('hook', '')}\n"]
    for section in script.get("sections", []):
        lines.append(f"[{section.get('name', '')}]\n{section.get('voiceover', '')}\n")
    return "\n".join(lines)


def build_storyboard(visuals: list[dict], sections: list[dict]) -> list[dict]:
    duration_by_name = {s.get("name", ""): s.get("duration", "") for s in sections}
    return [
        {
            "section": v["section"],
            "role": v.get("role", ""),
            "duration": duration_by_name.get(v["section"], ""),
            "visual_idea": v.get("visual_idea", ""),
            "camera_idea": v.get("camera_idea", ""),
            "scene_idea": v.get("scene_idea", ""),
        }
        for v in visuals
    ]


def build_visual_prompts(visuals: list[dict]) -> list[dict]:
    prompts = []
    for v in visuals:
        b_roll = ", ".join(v.get("b_roll", []) or [])
        prompt = f"{v.get('visual_idea', '')} {v.get('camera_idea', '')} {v.get('scene_idea', '')}".strip()
        prompts.append({
            "section": v["section"],
            "prompt": prompt,
            "b_roll_suggestions": v.get("b_roll", []),
            "raw_b_roll_text": b_roll,
        })
    return prompts


def build_thumbnail(script: dict, context_dict: dict, originality_eval: dict) -> dict:
    title = script.get("title", "")
    words = [w for w in title.split() if len(w) > 2][:4]
    return {
        "concept": script.get("thumbnail_concept", "") or context_dict.get("thumbnail_direction", ""),
        "text_overlay_suggestion": " ".join(words),
        "style_notes": "Tek ana nesne, yüksek kontrast, en fazla 3-4 kelime, tek güçlü gizem işareti.",
        "originality_risk": originality_eval.get("overall_score", 100) < 60,
        "reference_direction": context_dict.get("thumbnail_direction", ""),
    }


def build_youtube_upload(script: dict, context_dict: dict, ceo_review: dict) -> dict:
    return {
        "title": script.get("title", ""),
        "description": script.get("description", ""),
        "tags": script.get("tags", []),
        "hashtags": context_dict.get("hashtags", []),
        "category": "Education",
        "language": script.get("language", "tr"),
        "visibility": "private",
        "publish_time_recommendation": context_dict.get("recommended_publish_time", ""),
        "ceo_approved": ceo_review.get("decision") == "APPROVE",
        "ceo_score": ceo_review.get("ceo_score", 0),
        "captions_file": "subtitle.srt",
        "voiceover_file": "voiceover.txt",
    }


def build_video_engine_handoff(script: dict, context_dict: dict, ceo_review: dict) -> dict:
    return {
        "status": "READY_FOR_VIDEO_ENGINE" if ceo_review.get("decision") == "APPROVE" else "NOT_READY",
        "title": script.get("title", ""),
        "language": script.get("language", "tr"),
        "target_duration_minutes": round(
            sum(textutil.estimate_seconds(s.get("voiceover", "")) for s in script.get("sections", [])) / 60, 1
        ),
        "voiceover_sections": script.get("sections", []),
        "storyboard_file": "storyboard.json",
        "visual_prompts_file": "visual_prompts.json",
        "subtitle_file": "subtitle.srt",
        "thumbnail_file": "thumbnail.json",
        "hashtags": context_dict.get("hashtags", []),
        "ceo_score": ceo_review.get("ceo_score", 0),
        "ceo_verdict": ceo_review.get("verdict_text", ""),
    }


def build_script_md(
    script: dict,
    context_dict: dict,
    ceo_review: dict,
    evaluations: dict,
    attempts: int,
    rejected_history: list[dict],
) -> str:
    lines = [
        "# SHP Script Agent V2 — Head Writer AI",
        "",
        f"**Durum:** {ceo_review['decision']}",
        f"**Başlık:** {script.get('title', '')}",
        f"**CEO puanı:** {ceo_review['ceo_score']}/100 (eşik: {ceo_review['approval_threshold']})",
        f"**Üretim modu:** {script.get('source_mode', 'unknown')}",
        f"**Deneme sayısı:** {attempts}",
        "",
        "## CEO sorusu",
        "",
        f"> {ceo_review['question']}",
        "",
        f"{ceo_review['verdict_text']}",
        "",
    ]
    if rejected_history:
        lines += ["## Önceki reddedilen denemeler", ""]
        for item in rejected_history:
            lines.append(f"- Deneme {item['attempt']}: puan {item['ceo_score']} — {', '.join(item['reasons']) or 'gerekçe yok'}")
        lines.append("")

    lines += ["## Hook", "", str(script.get("hook", "")), ""]
    if script.get("alt_hooks"):
        lines += ["**Alternatif hook'lar:**", *[f"- {h}" for h in script["alt_hooks"]], ""]

    lines += ["## Tam senaryo", ""]
    for section in script.get("sections", []):
        lines += [f"### {section.get('name', 'Bölüm')} — {section.get('duration', '')}", "", str(section.get("voiceover", "")), ""]

    lines += [
        "## Motor değerlendirmeleri",
        "",
        f"- Merak (Curiosity): {evaluations['curiosity']['overall_score']}/100 — {'GEÇTİ' if evaluations['curiosity']['overall_pass'] else 'ZAYIF'}",
        f"- İzlenme süresi (Retention): {evaluations['retention']['overall_score']}/100 — {'GEÇTİ' if evaluations['retention']['overall_pass'] else 'ZAYIF'}",
        f"- Duygu eğrisi (Emotion): {evaluations['emotion']['curve_match_score']}/100",
        f"- Özgünlük (Originality): {evaluations['originality']['overall_score']}/100 — {len(evaluations['originality']['flagged_sentences'])} risk işaretlendi",
        f"- Kanıt (Fact): {evaluations['fact']['overall_score']}/100 — {evaluations['fact']['unverified_claim_count']} doğrulanmamış iddia",
        "",
        "## Thumbnail konsepti",
        "",
        str(script.get("thumbnail_concept", "")),
        "",
        "## Açıklama",
        "",
        str(script.get("description", "")),
        "",
        "## Etiketler",
        "",
        ", ".join(script.get("tags", [])),
        "",
        "## Script Doctor günlüğü",
        "",
        *([f"- {entry}" for entry in script.get("doctor_log", [])] or ["- Değişiklik gerekmedi."]),
        "",
    ]
    return "\n".join(lines)


def write_all(
    script: dict,
    context_dict: dict,
    knowledge: dict,
    story_dna_plan: dict,
    evaluations: dict,
    ceo_review: dict,
    visuals: list[dict],
    attempts: int,
    rejected_history: list[dict],
) -> None:
    sections = script.get("sections", [])

    (OUTPUT_DIR / "script.json").write_text(
        json.dumps(
            {
                "agent": "SHP Script Agent V2",
                "status": ceo_review["decision"],
                "attempts": attempts,
                "context": context_dict,
                "knowledge": knowledge,
                "story_dna_plan": story_dna_plan,
                "script": script,
                "evaluations": evaluations,
                "ceo_review": ceo_review,
                "rejected_history": rejected_history,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    (OUTPUT_DIR / "script.md").write_text(
        build_script_md(script, context_dict, ceo_review, evaluations, attempts, rejected_history), encoding="utf-8"
    )

    (OUTPUT_DIR / "storyboard.json").write_text(
        json.dumps(build_storyboard(visuals, sections), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (OUTPUT_DIR / "visual_prompts.json").write_text(
        json.dumps(build_visual_prompts(visuals), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (OUTPUT_DIR / "voiceover.txt").write_text(build_voiceover_txt(script), encoding="utf-8")
    (OUTPUT_DIR / "subtitle.srt").write_text(build_subtitle_srt(sections), encoding="utf-8")

    thumbnail = build_thumbnail(script, context_dict, evaluations["originality"])
    (OUTPUT_DIR / "thumbnail.json").write_text(json.dumps(thumbnail, ensure_ascii=False, indent=2), encoding="utf-8")

    youtube_upload = build_youtube_upload(script, context_dict, ceo_review)
    (OUTPUT_DIR / "youtube_upload.json").write_text(json.dumps(youtube_upload, ensure_ascii=False, indent=2), encoding="utf-8")

    handoff = build_video_engine_handoff(script, context_dict, ceo_review)
    (OUTPUT_DIR / "video_engine_handoff.json").write_text(json.dumps(handoff, ensure_ascii=False, indent=2), encoding="utf-8")
