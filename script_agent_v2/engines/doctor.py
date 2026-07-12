"""12. SCRIPT DOCTOR

The harshest editor SHP has. Strips filler, weak openings, repetition,
generic transitions and low-curiosity stretches out of the draft the Script
Generator produced, calling the other engines' `evaluate()` functions to
find what is still weak and rewriting it — with GROQ when available,
otherwise with deterministic punch-up rules. Runs multiple passes until the
script clears every gate or the pass budget runs out.
"""

from __future__ import annotations

import difflib
import re

from script_agent_v2 import textutil
from script_agent_v2.engines import curiosity_engine, emotion_engine, fact_engine, originality_engine, retention_engine
from script_agent_v2.llm import LLM

MAX_PASSES = 2
DUPLICATE_SIMILARITY_THRESHOLD = 0.85

REWRITE_SECTION_SYSTEM_PROMPT = (
    "Sen SHP Script Doctor'sın: acımasız bir belgesel editörüsün. Sana zayıf bir bölüm seslendirmesi ve "
    "sorunu vereceğim. Aynı bilgiyi koru ama sorunu çöz, jenerik ifade kullanma, tek bir güçlü versiyon üret. "
    "JSON döndür: {\"voiceover\": \"...\"}"
)

PUNCHY_OPENERS = [
    "Ama asıl gerçek çok daha karanlıktı.",
    "Kayıtlar bir şeyi gizliyordu.",
    "Kimsenin anlatmadığı kısım burada başlıyor.",
]


def _word_boundary_pattern(phrase: str) -> re.Pattern:
    # \b alone is unreliable across a phrase that starts/ends with a space,
    # so anchor on "not preceded/followed by a word character" instead —
    # this stops "sırada" from matching inside "sıradan".
    return re.compile(r"(?<!\w)" + re.escape(phrase) + r"(?!\w)", re.IGNORECASE)


def _strip_banned_phrases(text: str, log: list[str]) -> str:
    result = text
    for phrase in textutil.BANNED_PHRASES:
        pattern = _word_boundary_pattern(phrase)
        if pattern.search(result):
            log.append(f"Yasaklı ifade kaldırıldı: '{phrase}'")
            result = pattern.sub("", result)
    return re.sub(r"\s{2,}", " ", result).strip()


def _swap_generic_transitions(text: str, log: list[str]) -> str:
    # Only strip a generic transition when it opens a sentence — splicing a
    # whole replacement sentence into the *middle* of one breaks grammar
    # (e.g. "Peki bundan sonra ne oldu?" -> "Peki Ama asıl ... ne oldu?").
    sentences = textutil.split_sentences(text)
    rebuilt = []
    for sentence in sentences:
        stripped = sentence
        for phrase in textutil.GENERIC_TRANSITIONS:
            pattern = re.compile(r"^\s*" + re.escape(phrase) + r"\s*,?\s*", re.IGNORECASE)
            if pattern.match(stripped):
                log.append(f"Sıradan geçiş '{phrase}' kaldırıldı.")
                stripped = pattern.sub("", stripped)
                if stripped:
                    stripped = stripped[0].upper() + stripped[1:]
                break
        rebuilt.append(stripped)
    return " ".join(s for s in rebuilt if s)


def _dedupe_repetition(sections: list[dict], log: list[str]) -> None:
    seen: list[tuple[str, int]] = []  # (sentence, section_index)
    for s_index, section in enumerate(sections):
        text = str(section.get("voiceover", ""))
        sentences = textutil.split_sentences(text)
        kept = []
        for sentence in sentences:
            is_duplicate = any(
                difflib.SequenceMatcher(None, textutil.normalize(sentence), textutil.normalize(prev)).ratio()
                >= DUPLICATE_SIMILARITY_THRESHOLD
                for prev, _ in seen
            )
            if is_duplicate:
                log.append(f"Tekrar eden cümle çıkarıldı ({section.get('name', '')}): '{sentence[:50]}...'")
                continue
            kept.append(sentence)
            seen.append((sentence, s_index))
        if not kept and sentences:
            # Never leave a section with no narration at all — an
            # empty section is worse than one duplicate sentence.
            kept = [sentences[0]]
        section["voiceover"] = " ".join(kept)


def _rewrite_section(section: dict, problem: str, llm: LLM, log: list[str]) -> None:
    text = str(section.get("voiceover", ""))
    if any(text.strip().startswith(opener) for opener in PUNCHY_OPENERS):
        log.append(f"Zaten güçlendirilmiş, tekrar uygulanmadı ({section.get('name', '')}).")
        return

    result = llm.complete_json(
        REWRITE_SECTION_SYSTEM_PROMPT,
        f"Bölüm: {section.get('name', '')}\nSorun: {problem}\nMetin: {text}",
        temperature=0.65,
    )
    if result and isinstance(result, dict) and result.get("voiceover"):
        section["voiceover"] = str(result["voiceover"])
        log.append(f"GROQ ile yeniden yazıldı ({section.get('name', '')}): {problem}")
    else:
        opener = PUNCHY_OPENERS[hash(section.get("name", "")) % len(PUNCHY_OPENERS)]
        section["voiceover"] = f"{opener} {text}".strip()
        log.append(f"Kural tabanlı güçlendirme uygulandı ({section.get('name', '')}): {problem}")


def _soften_unverified_claims(sections: list[dict], fact_eval: dict, log: list[str]) -> None:
    by_section = {n["section"]: n["claims"] for n in fact_eval.get("section_notes", [])}
    for section in sections:
        claims = by_section.get(section.get("name", ""), [])
        text = str(section.get("voiceover", ""))
        for claim in claims:
            if claim["confidence"] != "düşük":
                continue
            sentence = claim["claim"]
            if sentence in text and not textutil.contains_any(sentence, textutil.CURIOSITY_WORDS + fact_engine.HEDGE_WORDS):
                hedged = "Kaynaklara göre, " + sentence[0].lower() + sentence[1:] if sentence else sentence
                text = text.replace(sentence, hedged, 1)
                log.append(f"Kanıtsız iddia temkinli hale getirildi ({section.get('name', '')}).")
        section["voiceover"] = text


def _apply_originality_fixes(sections: list[dict], originality_eval: dict, log: list[str]) -> None:
    by_section: dict[str, list[dict]] = {}
    for flag in originality_eval.get("flagged_sentences", []):
        by_section.setdefault(flag["section"], []).append(flag)

    for section in sections:
        flags = by_section.get(section.get("name", ""))
        if not flags:
            continue
        text = str(section.get("voiceover", ""))
        for flag in flags:
            if flag["sentence"] in text:
                text = text.replace(flag["sentence"], flag["suggested_alternative"], 1)
                log.append(f"Özgünlük riski taşıyan cümle değiştirildi ({section.get('name', '')}).")
        section["voiceover"] = text


def review_and_fix(
    script: dict,
    llm: LLM,
    curiosity_plan: dict,
    retention_plan: dict,
    emotion_plan: dict,
    originality_plan: dict,
    fact_ledger: list[dict],
) -> dict:
    log: list[str] = []
    sections = script.get("sections", [])

    for section in sections:
        section["voiceover"] = _strip_banned_phrases(str(section.get("voiceover", "")), log)
        section["voiceover"] = _swap_generic_transitions(section["voiceover"], log)
    script["hook"] = _strip_banned_phrases(str(script.get("hook", "")), log)

    _dedupe_repetition(sections, log)

    for _pass_index in range(MAX_PASSES):
        curiosity_eval = curiosity_engine.evaluate(sections, curiosity_plan)
        retention_eval = retention_engine.evaluate(sections, retention_plan)
        emotion_eval = emotion_engine.evaluate(sections, emotion_plan)
        originality_eval = originality_engine.evaluate(sections, originality_plan, llm)
        fact_eval = fact_engine.evaluate(sections, fact_ledger)

        weak_names = set(curiosity_eval.get("weak_sections", []))
        for checkpoint in retention_eval.get("checkpoints", []):
            if checkpoint["drop_risk"] == "yüksek":
                weak_names.add(checkpoint["covering_section"])
        for mismatch in emotion_eval.get("mismatches", []):
            weak_names.add(mismatch["section"])

        by_name = {s.get("name", ""): s for s in sections}
        for name in weak_names:
            if name in by_name:
                problem = "Merak/izlenme süresi puanı düşük; daha güçlü bir bilgi boşluğu aç."
                if name in {m["section"] for m in emotion_eval.get("mismatches", [])}:
                    problem += " Ayrıca bu bölümün duygusu hedeften sapıyor; hedef duyguya uygun kelimeler kullan."
                _rewrite_section(by_name[name], problem, llm, log)

        _apply_originality_fixes(sections, originality_eval, log)
        _soften_unverified_claims(sections, fact_eval, log)

        if (
            curiosity_eval["overall_pass"]
            and retention_eval["overall_pass"]
            and originality_eval["overall_pass"]
            and emotion_eval["overall_pass"]
        ):
            break

    script["sections"] = sections
    script["doctor_log"] = log
    script["doctor_passes"] = MAX_PASSES
    return script
