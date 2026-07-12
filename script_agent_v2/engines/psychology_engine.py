"""3. PSYCHOLOGY ENGINE

Understands human attention mechanics and exposes a single reusable
`score()` function that every later engine (Curiosity, Retention, Script
Doctor, CEO Reviewer) calls so the whole pipeline judges text the same way.

Dimensions scored (0-100 each): curiosity, reward_expectation, surprise,
novelty, pattern_interruption, information_gap, dopamine_loop.
"""

from __future__ import annotations

import re

from script_agent_v2 import textutil


def plan(context_dict: dict) -> dict:
    """Pre-generation target profile: which psychological levers this
    specific video should lean on hardest, based on SHP's brand and the
    audience it already knows converts (growth-advisor engagement data)."""
    return {
        "dimensions": [
            "curiosity", "reward_expectation", "surprise", "novelty",
            "pattern_interruption", "information_gap", "dopamine_loop",
        ],
        "minimum_pass_score": 55,
        "priority_dimensions": ["curiosity", "information_gap", "surprise"],
        "note": "Her bölüm en az bir açık bilgi boşluğu (information gap) taşımalı; boşluk sonraki bölümde kapanmalı.",
    }


def _pattern_interruption_score(text: str) -> int:
    sentences = textutil.split_sentences(text)
    if len(sentences) < 2:
        return 20
    lengths = [textutil.word_count(s) for s in sentences if s]
    if not lengths:
        return 20
    variance = max(lengths) - min(lengths)
    short_sentences = sum(1 for l in lengths if l <= 5)
    return min(100, variance * 4 + short_sentences * 15)


def score(text: str) -> dict:
    if not text or not text.strip():
        return {
            "curiosity": 0, "reward_expectation": 0, "surprise": 0, "novelty": 0,
            "pattern_interruption": 0, "information_gap": 0, "dopamine_loop": 0, "average": 0,
        }

    hits = textutil.trigger_hits(text)
    curiosity = min(100, len(hits.get("soru", [])) * 25 + len(hits.get("gizem", [])) * 20 + (25 if "?" in text else 0))
    reward_expectation = min(100, len(hits.get("vaat", [])) * 35 + len(hits.get("servet", [])) * 15)
    surprise = min(100, len(hits.get("saskinlik", [])) * 30 + len(textutil.contains_any(text, textutil.SURPRISE_WORDS)) * 20)
    novelty = min(100, len(re.findall(r"\b\d{2,4}\b", text)) * 20 + len(hits.get("gizem", [])) * 10)
    pattern_interruption = _pattern_interruption_score(text)
    information_gap = min(100, len(hits.get("vaat", [])) * 30 + len(hits.get("soru", [])) * 25)
    dopamine_loop = round((curiosity + reward_expectation + information_gap) / 3)

    values = [curiosity, reward_expectation, surprise, novelty, pattern_interruption, information_gap, dopamine_loop]
    return {
        "curiosity": curiosity,
        "reward_expectation": reward_expectation,
        "surprise": surprise,
        "novelty": novelty,
        "pattern_interruption": pattern_interruption,
        "information_gap": information_gap,
        "dopamine_loop": dopamine_loop,
        "average": round(sum(values) / len(values)),
    }
