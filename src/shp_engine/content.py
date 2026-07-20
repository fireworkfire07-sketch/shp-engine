from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Scene:
    heading: str
    body: str
    duration: float = 4.0


def create_scenes(topic: str) -> list[Scene]:
    """Create a complete fallback story without requiring a paid API."""
    clean = topic.strip()
    if not clean:
        raise ValueError("Topic cannot be empty.")

    return [
        Scene(f"{clean}: Gizli Hikâye", "Gördüğümüz şey, hikâyenin yalnızca başlangıcı."),
        Scene("Merak Uyandıran Soru", f"{clean} neden yüzyıllardır insanların dikkatini çekiyor?"),
        Scene("Geçmiş", f"{clean} hakkındaki bilgiler kuşaktan kuşağa aktarıldı ve zamanla değişti."),
        Scene("Bugün", f"Bilim ve teknoloji, {clean} konusuna artık bambaşka bir gözle bakıyor."),
        Scene("Şaşırtıcı Gerçek", "En güçlü ayrıntılar çoğu zaman gözümüzün önünde saklıdır."),
        Scene("Sonuç", f"{clean} hakkında bildiklerimiz, keşfedileceklerin yalnızca küçük bir kısmı."),
    ]
