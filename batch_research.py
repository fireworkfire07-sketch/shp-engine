from __future__ import annotations

import json
import os
import subprocess
import sys
import unicodedata
import re
from pathlib import Path

ROOT = Path("projects")


def slugify(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_text).strip("-").lower()
    return slug or "youtube-arastirma"


def main() -> None:
    if not os.getenv("YOUTUBE_API_KEY", "").strip():
        raise SystemExit("YOUTUBE_API_KEY bulunamadi.")

    raw = " ".join(sys.argv[1:]).strip()
    if not raw:
        raw = "Bitkilerin Gizli Tarihi, Sıfırdan Zirveye, Yapay Zeka Haberleri, Psikoloji Hikayeleri, Gizemli Tarih"

    topics = [item.strip() for item in raw.split(",") if item.strip()]
    if not topics:
        raise SystemExit("En az bir konu gerekli.")

    results = []
    for topic in topics:
        print(f"\n=== ANALIZ: {topic} ===")
        completed = subprocess.run([sys.executable, "commander.py", topic], check=False)
        if completed.returncode != 0:
            results.append({"topic": topic, "error": f"commander exit code {completed.returncode}"})
            continue

        analysis_path = ROOT / slugify(topic) / "analysis.json"
        if not analysis_path.exists():
            results.append({"topic": topic, "error": "analysis.json bulunamadi"})
            continue

        data = json.loads(analysis_path.read_text(encoding="utf-8"))
        results.append(
            {
                "topic": topic,
                "niche_score": data.get("niche_score", 0),
                "decision": data.get("decision", ""),
                "videos_analyzed": data.get("videos_analyzed", 0),
                "metrics": data.get("metrics", {}),
                "report": str(ROOT / slugify(topic) / "report.md"),
            }
        )

    ranked = sorted(results, key=lambda item: item.get("niche_score", -1), reverse=True)
    ROOT.mkdir(exist_ok=True)
    (ROOT / "batch-ranking.json").write_text(
        json.dumps(ranked, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    lines = [
        "# SHP Niş Karşılaştırma Raporu",
        "",
        "| Sıra | Niş | Puan | Karar | Medyan günlük izlenme | Rapor |",
        "|---:|---|---:|---|---:|---|",
    ]
    for index, item in enumerate(ranked, start=1):
        metrics = item.get("metrics", {})
        score = item.get("niche_score", "HATA")
        decision = item.get("decision", item.get("error", ""))
        report = item.get("report", "")
        report_link = f"[Aç]({report})" if report else "-"
        lines.append(
            f"| {index} | {item['topic']} | {score} | {decision} | "
            f"{metrics.get('median_views_per_day', '-')} | {report_link} |"
        )

    lines.extend(
        [
            "",
            "## Karar kuralı",
            "",
            "En yüksek puanlı iki niş için önce 5'er video test edilir. İzlenme doğrulanmadan tam otomasyona geçilmez.",
        ]
    )
    (ROOT / "batch-ranking.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("\n=== SIRALAMA ===")
    for index, item in enumerate(ranked, start=1):
        print(f"{index}. {item['topic']}: {item.get('niche_score', 'HATA')}")
    print("Rapor: projects/batch-ranking.md")


if __name__ == "__main__":
    main()
