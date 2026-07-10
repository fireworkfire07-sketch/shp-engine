from __future__ import annotations

import json
from pathlib import Path

from story_score import score_title

ROOT = Path("projects")


def main() -> None:
    rows = []

    for analysis_path in ROOT.glob("*/analysis.json"):
        data = json.loads(analysis_path.read_text(encoding="utf-8"))
        topic = data.get("topic", analysis_path.parent.name)

        for video in data.get("videos", []):
            result = score_title(video.get("title", ""))
            rows.append(
                {
                    "topic": topic,
                    "title": video.get("title", ""),
                    "views_per_day": video.get("views_per_day", 0),
                    "story_score": result["score"],
                    "verdict": result["verdict"],
                    "url": video.get("url", ""),
                }
            )

    rows.sort(key=lambda item: (item["story_score"], item["views_per_day"]), reverse=True)

    report_rows = []
    for index, item in enumerate(rows[:50], start=1):
        title = item["title"].replace("|", "-")
        report_rows.append(
            f"| {index} | {item['story_score']} | {item['views_per_day']} | "
            f"{item['topic']} | {title} | [Aç]({item['url']}) |"
        )

    report = f"""# SHP Hikâye DNA Raporu

Bu rapor, gerçek YouTube başlıklarını **merak, gizem, çatışma, şaşırtıcılık ve ansiklopedi dili** açısından puanlar.

| # | Hikâye puanı | Günlük izlenme | Niş | Başlık | Video |
|---:|---:|---:|---|---|---|
{chr(10).join(report_rows)}

## SHP içerik yasası

1. Önce ilgiyi kazan, sonra bilgiyi ver.
2. Bitki veya konu kahraman değil; insan hikâyesinin aracıdır.
3. Her başlıkta en az bir güçlü tetikleyici bulunmalıdır: gizem, yasak, ölüm, servet, ihanet, savaş veya şaşırtıcı soru.
4. `Nedir`, `faydaları`, `özellikleri`, `hakkında` gibi ansiklopedi kalıpları cezalandırılır.
5. Başlığın verdiği merak videoda mutlaka karşılanmalıdır.
"""

    (ROOT / "story-dna.md").write_text(report, encoding="utf-8")
    (ROOT / "story-dna.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Hikâye DNA raporu oluşturuldu: {len(rows)} başlık puanlandı.")


if __name__ == "__main__":
    main()
