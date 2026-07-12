"""6. RETENTION ENGINE

Predicts audience drop points at the checkpoints that matter most on
YouTube: 0-3s, 3-10s, 30s, 1min, 3min, and the ending. Scores whichever
generated section covers each checkpoint and flags weak coverage for
Script Doctor to rewrite.
"""

from __future__ import annotations

from script_agent_v2 import textutil
from script_agent_v2.engines import psychology_engine

CHECKPOINTS_SECONDS = [3, 10, 30, 60, 180]


def plan(context_dict: dict) -> dict:
    return {
        "checkpoints_seconds": CHECKPOINTS_SECONDS,
        "checkpoint_directives": {
            3: "İlk 3 saniyede tek güçlü görüntü veya iddia; giriş cümlesi yok.",
            10: "İlk 10 saniyede izleyiciye kalmak için somut bir sebep verilmiş olmalı.",
            30: "30. saniyede konu netleşmiş, ilk merak açılmış olmalı.",
            60: "1. dakikada yeni bir bilgi katmanı veya küçük bir sürpriz gelmeli.",
            180: "3. dakikada ana çatışma veya gizem derinleşmiş olmalı.",
        },
        "ending_directive": "Final, açılıştaki soruyu kapatmalı ve tek net izlenim bırakmalı.",
        "seed_hook": context_dict.get("first_3_seconds", ""),
    }


def _section_boundaries(sections: list[dict]) -> list[tuple[str, float, float]]:
    boundaries = []
    elapsed = 0.0
    for section in sections:
        duration = textutil.estimate_seconds(str(section.get("voiceover", "")))
        boundaries.append((section.get("name", ""), elapsed, elapsed + duration))
        elapsed += duration
    return boundaries


def _section_at(boundaries: list[tuple[str, float, float]], t: float) -> tuple[str, float, float] | None:
    for name, start, end in boundaries:
        if start <= t < end or (t >= boundaries[-1][2] and (name, start, end) == boundaries[-1]):
            return (name, start, end)
    return boundaries[-1] if boundaries else None


def evaluate(sections: list[dict], retention_plan: dict) -> dict:
    if not sections:
        return {"checkpoints": [], "weak_checkpoints": [], "overall_pass": False, "overall_score": 0}

    boundaries = _section_boundaries(sections)
    by_name = {s.get("name", ""): str(s.get("voiceover", "")) for s in sections}

    checkpoints = []
    weak = []
    for t in retention_plan.get("checkpoints_seconds", CHECKPOINTS_SECONDS):
        hit = _section_at(boundaries, t)
        if not hit:
            continue
        name, start, end = hit
        text = by_name.get(name, "")
        result = psychology_engine.score(text)
        drop_risk = "düşük" if result["average"] >= 55 else ("orta" if result["average"] >= 35 else "yüksek")
        if drop_risk == "yüksek":
            weak.append(f"{t}s ({name})")
        checkpoints.append({
            "checkpoint_seconds": t,
            "covering_section": name,
            "psychology_score": result["average"],
            "drop_risk": drop_risk,
        })

    ending_name = sections[-1].get("name", "")
    ending_text = str(sections[-1].get("voiceover", ""))
    ending_score = psychology_engine.score(ending_text)
    ending_risk = "düşük" if ending_score["average"] >= 50 else ("orta" if ending_score["average"] >= 30 else "yüksek")
    if ending_risk == "yüksek":
        weak.append(f"final ({ending_name})")
    checkpoints.append({
        "checkpoint_seconds": "ending",
        "covering_section": ending_name,
        "psychology_score": ending_score["average"],
        "drop_risk": ending_risk,
    })

    overall_score = round(sum(c["psychology_score"] for c in checkpoints) / len(checkpoints))
    return {
        "checkpoints": checkpoints,
        "weak_checkpoints": weak,
        "overall_pass": not weak,
        "overall_score": overall_score,
    }
