"""1. KNOWLEDGE ENGINE

Researches the topic before a single narration sentence is written. Extracts
historical facts, uncommon information, myths, controversies, scientific
findings, surprising details, a timeline, key people and locations. Avoids
generic encyclopedia information — every entry must be a specific, checkable
claim, not a vague statement.
"""

from __future__ import annotations

from script_agent_v2.llm import LLM

SYSTEM_PROMPT = (
    "Sen SHP Knowledge Engine'sin: 'The Secret History of Plants' belgesel stüdyosunun araştırma başıdır. "
    "Konu hakkında derin, SPESİFİK ve doğrulanabilir araştırma çıkar. Asla ansiklopedik genel bilgi verme "
    "(örnek: 'bu bitki dünyada yetişir' gibi cümleler yasak). Her madde somut bir isim, tarih, yer veya sayı içermeli. "
    "Çıktın geçerli JSON olsun ve şu alanları içersin: "
    "facts (dizi: {text, category: 'tarihsel'|'bilimsel'|'kültürel', confidence: 'yüksek'|'orta'|'düşük'}), "
    "uncommon_information (dizi metin), myths (dizi metin), controversies (dizi metin), "
    "scientific_findings (dizi metin), surprising_details (dizi metin), "
    "timeline (dizi: {date, event}), key_people (dizi: {name, role}), locations (dizi: {name, significance})."
)


def _fallback(context_dict: dict) -> dict:
    """No GROQ key: build an honest, sparse research seed from what SHP
    already has (competitor reference, brand themes) instead of inventing
    facts. Every field is explicitly marked as unresearched so downstream
    engines (Fact Engine, CEO Reviewer) treat it as low-confidence."""
    topic = context_dict.get("topic") or "SHP konusu"
    video_dna = context_dict.get("video_dna") or {}
    lead = str(video_dna.get("description_preview", "")).strip()

    facts = []
    if lead:
        truncated = lead[:180]
        if len(lead) > 180:
            truncated = truncated.rsplit(" ", 1)[0] + "…"
        facts.append({
            "text": f"Referans video açıklamasından ipucu: {truncated}",
            "category": "kültürel",
            "confidence": "düşük",
        })

    return {
        "facts": facts,
        "uncommon_information": [],
        "myths": [],
        "controversies": [],
        "scientific_findings": [],
        "surprising_details": [],
        "timeline": [],
        "key_people": [],
        "locations": [],
        "research_mode": "rule_based_fallback",
        "research_note": (
            f"GEMINI_API_KEY (ve OPENAI_API_KEY, GROQ_API_KEY) yok; '{topic}' için derin araştırma yapılamadı. "
            "Script Doctor bu konudaki tüm iddiaları 'düşük güven' olarak işaretleyecek."
        ),
    }


def run(context_dict: dict, llm: LLM) -> dict:
    topic = context_dict.get("topic") or ""
    niche = context_dict.get("niche") or ""
    user = (
        f"Konu: {topic}\nNiş: {niche}\n"
        f"Rakip referansı: {context_dict.get('competitor_reference', {})}\n"
        "SHP markası sadece doğa, bitki, mantar, orman, baharat, ilaç, tohum konularını işler; "
        "insan hikayesi bitki/doğa aracılığıyla anlatılır. Araştırmayı bu çerçevede derinleştir."
    )
    result = llm.complete_json(SYSTEM_PROMPT, user, temperature=0.4)
    if not result or not isinstance(result, dict):
        return _fallback(context_dict)

    result.setdefault("facts", [])
    result.setdefault("timeline", [])
    result.setdefault("key_people", [])
    result.setdefault("locations", [])
    result["research_mode"] = llm.last_provider or "unknown"
    return result
