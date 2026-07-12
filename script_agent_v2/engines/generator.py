"""11. SCRIPT GENERATOR

Assembles the actual script: title, hook, full narration, scene structure,
narration timing, thumbnail concept, description and tags. Every other
engine's plan feeds into this one prompt so the first draft is already
built to pass Curiosity, Retention, Emotion, Originality and Fact review —
Script Doctor exists to catch what still slips through.
"""

from __future__ import annotations

from script_agent_v2 import textutil
from script_agent_v2.llm import LLM
from story_score import score_title

SYSTEM_PROMPT = (
    "Sen SHP Script Generator'sın: 'The Secret History of Plants' belgesel stüdyosunun Baş Yazarısın. "
    "Metin üreten bir araç değil, izleyiciyi son saniyeye kadar ekranda tutmayı hedefleyen bir Head Writer AI'sın. "
    "SHP tarzı: yavaş, sinematik, premium, meraklı, bilimsel, duygusal — asla sansasyonel veya sahte. "
    "Bitki/doğa asla kahraman değildir; insan hikâyesinin aracıdır. "
    "KESİNLİKLE YASAK: 'Bu videoda', 'Başlayalım', 'Sonuna kadar izleyin', 'Hoş geldiniz', jenerik AI açılışları, "
    "tekrarlanan cümleler, dolgu cümleler, kanıtsız kesin iddialar. "
    "Sana araştırma verisi, yapı hedefleri, izleyici profili, merak/izlenme/duygu/özgünlük/kanıt planları vereceğim. "
    "Bunların HEPSİNİ kullanarak tek bir JSON senaryo üret: "
    "{\"title\": \"...\", \"alt_titles\": [\"...\" x9], \"hook\": \"...\", \"alt_hooks\": [\"...\" x2], "
    "\"sections\": [{\"name\": \"...\", \"duration\": \"0:00-0:30\", \"voiceover\": \"...\"}], "
    "\"thumbnail_concept\": \"...\", \"description\": \"...\", \"tags\": [\"...\"]}. "
    "sections dizisi tam olarak istenen bölüm sayısında olmalı."
)


def _build_user_prompt(
    context_dict: dict,
    knowledge: dict,
    story_dna_plan: dict,
    psychology_plan: dict,
    audience_profile: dict,
    curiosity_plan: dict,
    retention_plan: dict,
    emotion_plan: dict,
    originality_plan: dict,
    fact_ledger: list[dict],
    memory_hints: dict,
    feedback: list[str] | None,
) -> str:
    lines = [
        f"KONU: {context_dict.get('topic', '')}",
        f"NİŞ: {context_dict.get('niche', '')}",
        f"HEDEF BÖLÜM SAYISI: {story_dna_plan.get('recommended_chapter_count', 7)}",
        f"HEDEF TOPLAM SÜRE (saniye): {story_dna_plan.get('target_duration_seconds', 420)}",
        f"AÇILIŞ STİLİ: {story_dna_plan.get('recommended_hook_style', '')}",
        f"KAPANIŞ STİLİ: {story_dna_plan.get('ending_style', '')}",
        f"PSİKOLOJİK ÖNCELİK: {', '.join(psychology_plan.get('priority_dimensions', []))} boyutlarını öncelikle hedefle. {psychology_plan.get('note', '')}",
        f"İZLEYİCİ PROFİLİ: {audience_profile.get('label', '')} — {audience_profile.get('vocabulary', '')}",
        f"MERAK HEDEFİ: her ~{curiosity_plan.get('gap_interval_seconds', 27)} saniyede yeni bir bilgi boşluğu aç.",
        f"İZLENME SÜRESİ KRİTİK NOKTALARI: {retention_plan.get('checkpoint_directives', {})}",
        f"DUYGU EĞRİSİ (sırayla): {emotion_plan.get('target_curve', [])}",
        f"KAÇINILACAK METİNLER (kopyalama riski): {originality_plan.get('avoid_corpus', [])}",
        f"ARAŞTIRMA BULGULARI: {knowledge}",
        f"KANIT DEFTERİ (bu iddiaları kullan, uydurma): {fact_ledger}",
        f"REKABET REFERANSI: {context_dict.get('competitor_reference', {})}",
        f"GEÇMİŞ SHP DERSLERİ: {memory_hints}",
        f"KANAL PERFORMANS DERSLERİ (gerçek yayınlanmış video verisinden, Learning Engine): {context_dict.get('channel_lessons', {})}",
    ]
    if feedback:
        lines.append("ÖNCEKİ TASLAK CEO TARAFINDAN REDDEDİLDİ. Şu sorunları düzelt: " + " | ".join(feedback))
    return "\n".join(lines)


def _pick_best_title(candidates: list[str]) -> tuple[str, list[str]]:
    scored = [(title, score_title(title)["score"]) for title in candidates if title]
    scored.sort(key=lambda pair: pair[1], reverse=True)
    if not scored:
        return "", []
    return scored[0][0], [title for title, _ in scored[1:]]


GENERIC_CONNECTIVES = [
    "kayıtların bir kısmı hâlâ tartışmalı; bu da hikâyeyi tek bir cümleyle kapatmayı imkânsız kılıyor.",
    "farklı kaynaklar farklı ayrıntılar aktarıyor; ortak nokta ise sonucun kimseyi ilgisiz bırakmaması.",
    "izleri takip ettikçe resmi anlatının anlatmadığı bir katman daha ortaya çıkıyor.",
    "asıl soru neyin olduğu değil, neden bu kadar uzun süre gölgede kaldığı.",
]


def _fallback(
    context_dict: dict,
    knowledge: dict,
    story_dna_plan: dict,
) -> dict:
    topic = context_dict.get("topic") or "İnsanlık Tarihini Değiştiren Gizemli Bitki"
    hook = context_dict.get("first_3_seconds") or f"{topic}, göründüğünden çok daha büyük bir sırrı saklıyor."
    chapter_count = story_dna_plan.get("recommended_chapter_count", 6)
    chapter_seconds = story_dna_plan.get("recommended_chapter_length_seconds", 60)

    facts = knowledge.get("facts", []) or []
    timeline = knowledge.get("timeline", []) or []
    myths = knowledge.get("myths", []) or []

    names = ["Açılış", "Köken", "İlk Kırılma", "Derinleşen Gizem", "Büyük Cevap", "Final"]
    if chapter_count > len(names):
        names = names[:-1] + [f"Bölüm {i}" for i in range(len(names), chapter_count - 1)] + [names[-1]]
    names = names[:chapter_count]

    sections = []
    elapsed = 0
    for index, name in enumerate(names):
        start, end = elapsed, elapsed + chapter_seconds
        if index == 0:
            body = hook + " Cevabı birazdan göreceksiniz; ama önce bu sırrın başladığı yere dönelim."
        elif index == len(names) - 1:
            body = "Bugün sıradan görünen bu hikâyenin geçmişte nasıl bir güç aracına dönüştüğünü bilmek, bakışımızı değiştiriyor."
        elif timeline and index - 1 < len(timeline):
            entry = timeline[index - 1]
            entry_text = f"{entry.get('date', '')}: {entry.get('event', '')}" if isinstance(entry, dict) else str(entry)
            body = f"{entry_text} Fakat resmi anlatı burada durmuyor; küçük ayrıntılar daha büyük bir hikâyeye işaret ediyor."
        elif myths and index - 1 < len(myths):
            body = f"Yaygın inanışa göre {myths[index - 1]} Ama kayıtlar farklı bir gerçeği işaret ediyor."
        elif facts and index - 1 < len(facts):
            fact = facts[index - 1]
            body = str(fact.get("text", fact) if isinstance(fact, dict) else fact) + " Bu tek başına bile hikâyenin yönünü değiştiriyor."
        else:
            connective = GENERIC_CONNECTIVES[index % len(GENERIC_CONNECTIVES)]
            body = f"{topic} konusunda {connective}"
        sections.append({"name": name, "duration": f"{start // 60}:{start % 60:02d}-{end // 60}:{end % 60:02d}", "voiceover": body})
        elapsed = end

    return {
        "title": topic,
        "alt_titles": [],
        "hook": hook,
        "alt_hooks": [],
        "sections": sections,
        "thumbnail_concept": context_dict.get("thumbnail_direction", "") or "Tek ana nesne, yüksek kontrast, gizem işareti.",
        "description": f"{topic}: {hook}",
        "tags": context_dict.get("keywords", [])[:8],
        "source_mode": "rule_based_fallback",
    }


def generate(
    context_dict: dict,
    llm: LLM,
    knowledge: dict,
    story_dna_plan: dict,
    psychology_plan: dict,
    audience_profile: dict,
    curiosity_plan: dict,
    retention_plan: dict,
    emotion_plan: dict,
    originality_plan: dict,
    fact_ledger: list[dict],
    memory_hints: dict,
    feedback: list[str] | None = None,
) -> dict:
    user_prompt = _build_user_prompt(
        context_dict, knowledge, story_dna_plan, psychology_plan, audience_profile, curiosity_plan,
        retention_plan, emotion_plan, originality_plan, fact_ledger, memory_hints, feedback,
    )
    result = llm.complete_json(SYSTEM_PROMPT, user_prompt, temperature=0.7)

    if not result or not isinstance(result, dict) or not result.get("sections"):
        return _fallback(context_dict, knowledge, story_dna_plan)

    candidates = [result.get("title", "")] + list(result.get("alt_titles", []) or [])
    best_title, remaining_titles = _pick_best_title([c for c in candidates if c])
    result["title"] = best_title or result.get("title", "")
    result["alt_titles"] = remaining_titles

    hooks = [h for h in [result.get("hook", "")] + list(result.get("alt_hooks", []) or []) if h]
    if hooks:
        hooks.sort(key=lambda h: sum(len(v) for v in textutil.trigger_hits(h).values()), reverse=True)
        result["hook"] = hooks[0]
        result["alt_hooks"] = hooks[1:]

    result.setdefault("tags", context_dict.get("keywords", [])[:8])
    result.setdefault("thumbnail_concept", context_dict.get("thumbnail_direction", ""))
    result["source_mode"] = "groq"
    return result
