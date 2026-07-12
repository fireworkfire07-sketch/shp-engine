"""8. ORIGINALITY ENGINE

Never copies. Builds an "avoid corpus" from competitor titles, the
reference video's title/description and SHP's own top-performing title
corpus, then checks every generated sentence for wording/example overlap
that would read as copied. Flags copyright risk and proposes an original
alternative for anything too close.
"""

from __future__ import annotations

from script_agent_v2 import textutil
from script_agent_v2.llm import LLM

SIMILARITY_RISK_THRESHOLD = 0.55

REWRITE_SYSTEM_PROMPT = (
    "Sen SHP Originality Engine'sin. Sana bir cümle ve onun neden rakip metne çok benzediğini vereceğim. "
    "Aynı anlamı, aynı bilgiyi koru ama tamamen farklı kelime ve cümle yapısıyla, SHP'nin sinematik "
    "Türkçe belgesel tonunda yeniden yaz. Sadece JSON döndür: {\"rewrite\": \"...\"}"
)


def plan(context_dict: dict) -> dict:
    corpus = []
    competitor_ref = context_dict.get("competitor_reference", {}) or {}
    if competitor_ref.get("strongest_video"):
        corpus.append(str(competitor_ref["strongest_video"]))

    video_dna = context_dict.get("video_dna") or {}
    if video_dna.get("title"):
        corpus.append(str(video_dna["title"]))
    if video_dna.get("description_preview"):
        corpus.append(str(video_dna["description_preview"]))

    return {
        "avoid_corpus": [c for c in corpus if c.strip()],
        "similarity_risk_threshold": SIMILARITY_RISK_THRESHOLD,
        "rule": "Rakip metni kopyalama; yalnızca izleyici ihtiyacı ve yapı öğrenilir.",
    }


def evaluate(sections: list[dict], originality_plan: dict, llm: LLM) -> dict:
    corpus = originality_plan.get("avoid_corpus", [])
    threshold = originality_plan.get("similarity_risk_threshold", SIMILARITY_RISK_THRESHOLD)
    flagged = []

    if corpus:
        for section in sections:
            for sentence in textutil.split_sentences(str(section.get("voiceover", ""))):
                if textutil.word_count(sentence) < 5:
                    continue
                best_overlap = max((textutil.jaccard_similarity(sentence, ref) for ref in corpus), default=0.0)
                if best_overlap >= threshold:
                    alternative = _rewrite(sentence, llm)
                    flagged.append({
                        "section": section.get("name", ""),
                        "sentence": sentence,
                        "overlap": round(best_overlap, 2),
                        "suggested_alternative": alternative,
                    })

    max_overlap = max((f["overlap"] for f in flagged), default=0.0)
    return {
        "flagged_sentences": flagged,
        "max_overlap": max_overlap,
        "overall_pass": max_overlap < threshold,
        "overall_score": round(100 * (1 - max_overlap)),
    }


def _rewrite(sentence: str, llm: LLM) -> str:
    result = llm.complete_json(REWRITE_SYSTEM_PROMPT, sentence, temperature=0.7)
    if result and isinstance(result, dict) and result.get("rewrite"):
        return str(result["rewrite"])
    words = sentence.split()
    if len(words) > 6:
        midpoint = len(words) // 2
        return " ".join(words[midpoint:] + words[:midpoint]) + " (elle yeniden yazılmalı)"
    return sentence + " (elle yeniden yazılmalı — otomatik alternatif üretilemedi)"
