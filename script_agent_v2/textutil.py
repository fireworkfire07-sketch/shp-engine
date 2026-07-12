"""Shared text primitives used by multiple engines: normalization, sentence
splitting, narration-time estimation and the psychological trigger lexicon.
Centralized so every engine scores text the same way.
"""

from __future__ import annotations

import re
import unicodedata

# Turkish documentary narration reads at roughly 2.3-2.6 words/second at a
# slow, cinematic pace (SHP style). Used to map words -> seconds everywhere.
WORDS_PER_SECOND = 2.4

TRIGGER_WORDS = {
    "gizem": ["gizli", "gizem", "sır", "saklı", "bilinmeyen", "yasak", "karanlık", "keşfedilmemiş"],
    "catisma": ["ölüm", "öldür", "savaş", "yıkıldı", "ihanet", "ceza", "lanet", "zehir", "tehlike", "tehdit"],
    "servet": ["servet", "zengin", "milyon", "milyar", "altın", "imparatorluk", "krallık", "güç"],
    "soru": ["neden", "nasıl", "kim", "ne oldu", "gerçek mi", "peki ya"],
    "saskinlik": ["inanılmaz", "şok", "şaşırtıcı", "kimse bilmiyor", "ilk kez", "asla", "meğer", "aslında"],
    "vaat": ["birazdan", "az sonra", "biraz sonra", "cevap", "sır çözülüyor", "sonunda", "işte o an"],
}

SURPRISE_WORDS = ["şaşırtıcı", "inanılmaz", "meğer", "aslında", "şok edici", "kimse bilmiyordu"]
TENSION_WORDS = ["tehlike", "risk", "çatışma", "savaş", "ölüm", "tehdit", "kriz", "sırra"]
DISCOVERY_WORDS = ["keşif", "ortaya çıktı", "bulundu", "kanıt", "çözüldü", "anlaşıldı", "gün yüzüne"]
SATISFACTION_WORDS = ["bugün", "sonuç olarak", "artık biliyoruz", "işte bu yüzden", "anlıyoruz ki"]
CURIOSITY_WORDS = ["neden", "nasıl", "kim", "peki", "ama asıl soru", "gerçekte"]

BANNED_PHRASES = [
    "bu videoda", "bu videomuzda", "başlayalım", "hadi başlayalım", "sonuna kadar izleyin",
    "videonun sonuna kadar", "hoş geldiniz", "merhaba arkadaşlar", "kanalımıza abone olmayı unutmayın",
    "bugünkü videomuzda", "let's begin", "in this video", "stay until the end", "welcome back",
    "sevgili izleyiciler", "günün konusu", "bu bölümde", "izlemeye devam edin",
]

GENERIC_TRANSITIONS = ["bundan sonra", "şimdi de", "devam edelim", "sırada", "peki şimdi"]


def normalize(text: str) -> str:
    # Turkish dotless "ı" (U+0131) has no NFKD decomposition and isn't ASCII,
    # so it silently vanished under encode("ascii", "ignore") below — which
    # fragmented almost every Turkish word ("yılında" -> "y", "l", "nda")
    # and corrupted every jaccard_similarity-based comparison (fact-checking,
    # originality/copy detection). Fold it to "i" before decomposition.
    lowered = (text or "").casefold().replace("ı", "i")
    normalized = unicodedata.normalize("NFKD", lowered)
    ascii_text = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", ascii_text).strip()


def word_count(text: str) -> int:
    return len(re.findall(r"[A-Za-zÇĞİÖŞÜçğıöşü0-9]+", text or ""))


def estimate_seconds(text: str) -> float:
    return round(word_count(text) / WORDS_PER_SECOND, 1)


def split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?…])\s+", (text or "").strip())
    return [p.strip() for p in parts if p.strip()]


def trigger_hits(text: str) -> dict[str, list[str]]:
    normalized = normalize(text)
    return {category: [w for w in words if normalize(w) in normalized] for category, words in TRIGGER_WORDS.items()}


def trigger_density(text: str) -> int:
    return sum(len(hits) for hits in trigger_hits(text).values())


def jaccard_similarity(a: str, b: str) -> float:
    tokens_a = set(re.findall(r"[a-z0-9]+", normalize(a)))
    tokens_b = set(re.findall(r"[a-z0-9]+", normalize(b)))
    if not tokens_a or not tokens_b:
        return 0.0
    return len(tokens_a & tokens_b) / len(tokens_a | tokens_b)


def contains_any(text: str, phrases: list[str]) -> list[str]:
    normalized = normalize(text)
    return [p for p in phrases if normalize(p) in normalized]
