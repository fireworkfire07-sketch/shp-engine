"""4. AUDIENCE ENGINE

Adapts tone, vocabulary and pacing to who is actually watching: history
lovers, documentary viewers, young viewers, older viewers, educational
audience. SHP's fixed core audience (company_handbook.md) is 18-45,
Netflix-documentary viewers — this engine fine-tunes around that baseline
using the topic itself and channel/competitor signals.
"""

from __future__ import annotations

from script_agent_v2 import textutil

PROFILES = {
    "documentary_viewers": {
        "label": "Netflix belgeseli izleyicisi (SHP çekirdek kitlesi)",
        "vocabulary": "Sinematik, akıcı, orta-üst seviye kelime dağarcığı; jargon açıklanır.",
        "pacing": "Yavaş açılış, sabırlı inşa, keskin ortadaki dönüş, sakin final.",
        "narration_person": "üçüncü tekil/çoğul, mesafeli anlatıcı sesi",
    },
    "history_lovers": {
        "label": "Tarih meraklısı",
        "vocabulary": "Tarihsel terimler net kullanılır, tarih/yer isimleri sık geçer.",
        "pacing": "Kronolojik ama sürprizle kesilen zaman çizgisi.",
        "narration_person": "üçüncü tekil, otoriter ama sıcak ton",
    },
    "young_viewers": {
        "label": "Genç izleyici (Shorts/algoritma keşfi)",
        "vocabulary": "Kısa cümleler, güncel ama abartısız dil, hızlı bilgi yoğunluğu.",
        "pacing": "İlk 3 saniyede şok, her 15-20 saniyede yeni kanca.",
        "narration_person": "ikinci tekile yakın, samimi ton",
    },
    "educational_audience": {
        "label": "Eğitim/bilim odaklı izleyici",
        "vocabulary": "Bilimsel doğruluk önde, iddialar kaynağa dayanır.",
        "pacing": "Kavram → kanıt → sonuç düzeni, tempo orta.",
        "narration_person": "üçüncü tekil, öğretici ama merak uyandıran ton",
    },
}

YOUNG_SIGNAL_WORDS = ["shorts", "trend", "viral", "keşfet", "fyp"]
SCIENCE_SIGNAL_WORDS = ["bilim", "bilimsel", "araştırma", "kanıt", "keşif"]


def run(context_dict: dict) -> dict:
    topic = context_dict.get("topic", "")
    keywords = " ".join(context_dict.get("keywords", []) or [])
    signal_text = f"{topic} {keywords}"

    if textutil.contains_any(signal_text, YOUNG_SIGNAL_WORDS):
        primary = "young_viewers"
    elif textutil.contains_any(signal_text, SCIENCE_SIGNAL_WORDS):
        primary = "educational_audience"
    elif textutil.trigger_hits(topic).get("gizem") or "tarih" in textutil.normalize(topic):
        primary = "history_lovers"
    else:
        primary = "documentary_viewers"

    profile = dict(PROFILES[primary])
    profile["profile_id"] = primary
    profile["secondary_profile"] = "documentary_viewers" if primary != "documentary_viewers" else "history_lovers"
    profile["age_range"] = "18-45"
    profile["brand_constraint"] = "SHP tarzı: yavaş, sinematik, premium, meraklı, bilimsel, duygusal — asla sansasyonel veya sahte."
    return profile
