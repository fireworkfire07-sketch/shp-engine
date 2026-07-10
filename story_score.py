from __future__ import annotations

import re
import unicodedata

TRIGGERS = {
    "gizem": ["gizli", "gizem", "sir", "sakli", "bilinmeyen", "yasak", "karanlik"],
    "catismа": ["olum", "oldur", "savas", "yikildi", "ihanet", "ceza", "lanet", "zehir"],
    "servet": ["servet", "zengin", "milyon", "milyar", "altin", "imparatorluk", "krallik"],
    "soru": ["neden", "nasil", "kim", "ne oldu", "gercek mi"],
    "saskinlik": ["inanilmaz", "sok", "sasirtici", "kimse bilmiyor", "ilk kez", "asla"],
}

WEAK_WORDS = ["nedir", "hakkinda", "ozellikleri", "faydalari", "tarihi", "rehberi", "bilgiler"]


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", text.lower()).strip()


def score_title(title: str) -> dict:
    text = normalize(title)
    length = len(title.strip())

    categories = {}
    score = 15

    for category, words in TRIGGERS.items():
        hits = [word for word in words if word in text]
        categories[category] = hits
        score += min(18, len(hits) * 9)

    if "?" in title:
        score += 8
    if 35 <= length <= 72:
        score += 10
    elif length > 95:
        score -= 10

    weak_hits = [word for word in WEAK_WORDS if word in text]
    score -= min(30, len(weak_hits) * 10)

    score = max(0, min(100, score))

    if score >= 80:
        verdict = "ZEHIRLI: Kaydirmayi durduracak kadar guclu."
    elif score >= 60:
        verdict = "GUCLU: Hikaye ve merak var, biraz daha keskinlestir."
    elif score >= 40:
        verdict = "ORTA: Bilgi var ama merak baskin degil."
    else:
        verdict = "ZAYIF: Ansiklopedi basligi gibi duruyor."

    return {
        "score": score,
        "verdict": verdict,
        "trigger_hits": categories,
        "weak_hits": weak_hits,
    }
