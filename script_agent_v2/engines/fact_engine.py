"""10. FACT ENGINE

No empty statements. Builds a fact ledger from the Knowledge Engine, then
scans every claim-like sentence in the generated script and tags it with a
source basis (historical/scientific/inference) and a confidence level. This
is what makes "no fake confidence" enforceable instead of aspirational.
"""

from __future__ import annotations

import re

from script_agent_v2 import textutil

CLAIM_PATTERN = re.compile(r"\d{2,4}|yüzyıl|MÖ|MS|kanıtlan|araştırma|bilim insan")
HEDGE_WORDS = ["muhtemelen", "olabilir", "iddia edil", "kaynaklara göre", "söylenir"]


def build_ledger(knowledge: dict) -> list[dict]:
    ledger = []
    for fact in knowledge.get("facts", []) or []:
        ledger.append({
            "text": str(fact.get("text", fact) if isinstance(fact, dict) else fact),
            "category": fact.get("category", "tarihsel") if isinstance(fact, dict) else "tarihsel",
            "confidence": fact.get("confidence", "orta") if isinstance(fact, dict) else "orta",
        })
    for item in knowledge.get("scientific_findings", []) or []:
        ledger.append({"text": str(item), "category": "bilimsel", "confidence": "orta"})
    for item in knowledge.get("timeline", []) or []:
        text = f"{item.get('date', '')}: {item.get('event', '')}" if isinstance(item, dict) else str(item)
        ledger.append({"text": text, "category": "tarihsel", "confidence": "orta"})
    for item in knowledge.get("uncommon_information", []) or []:
        ledger.append({"text": str(item), "category": "kültürel", "confidence": "orta"})
    return ledger


def _best_match(sentence: str, ledger: list[dict]) -> dict | None:
    best = None
    best_score = 0.0
    for entry in ledger:
        overlap = textutil.jaccard_similarity(sentence, entry["text"])
        if overlap > best_score:
            best_score = overlap
            best = entry
    return best if best_score >= 0.15 else None


def evaluate(sections: list[dict], ledger: list[dict]) -> dict:
    section_notes = []
    unverified_count = 0
    total_claims = 0

    for section in sections:
        text = str(section.get("voiceover", ""))
        notes = []
        for sentence in textutil.split_sentences(text):
            if not CLAIM_PATTERN.search(sentence.lower()):
                continue
            total_claims += 1
            match = _best_match(sentence, ledger)
            is_hedged = bool(textutil.contains_any(sentence, HEDGE_WORDS))
            if match:
                confidence = match["confidence"]
                basis = match["category"]
            elif is_hedged:
                confidence = "orta"
                basis = "belirtilmemiş (yazarca temkinli ifade edilmiş)"
            else:
                confidence = "düşük"
                basis = "doğrulanmamış"
                unverified_count += 1
            notes.append({"claim": sentence, "source_basis": basis, "confidence": confidence})
        section_notes.append({"section": section.get("name", ""), "claims": notes})

    unverified_ratio = round(unverified_count / total_claims, 2) if total_claims else 0.0
    return {
        "section_notes": section_notes,
        "total_claims": total_claims,
        "unverified_claim_count": unverified_count,
        "unverified_ratio": unverified_ratio,
        "overall_pass": unverified_ratio <= 0.35,
        "overall_score": round(100 * (1 - unverified_ratio)),
    }
