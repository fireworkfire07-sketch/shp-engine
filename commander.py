from pathlib import Path
import json
from datetime import datetime

ROOT = Path("projects")
ROOT.mkdir(exist_ok=True)

def slugify(text):
    return (
        text.lower()
        .replace(" ", "-")
        .replace("ı", "i")
        .replace("ğ", "g")
        .replace("ü", "u")
        .replace("ş", "s")
        .replace("ö", "o")
        .replace("ç", "c")
    )

def save(path, content):
    path.write_text(content, encoding="utf-8")

topic = input("Topic: ").strip()

if not topic:
    raise SystemExit("Topic is required.")

project_name = slugify(topic)
project_dir = ROOT / project_name
project_dir.mkdir(exist_ok=True)

analysis = {
    "topic": topic,
    "created_at": datetime.utcnow().isoformat(),
    "status": "draft",
    "scores": {
        "hidden_story": None,
        "historical_impact": None,
        "curiosity": None,
        "visual_potential": None,
        "scientific_reliability": None,
        "evergreen": None
    },
    "final_score": None,
    "decision": None
}

save(project_dir / "analysis.json", json.dumps(analysis, indent=2))
save(project_dir / "titles.md", "# Title Options\n\n")
save(project_dir / "thumbnail.md", "# Thumbnail Concepts\n\n")
save(project_dir / "hook.md", "# Hook Options\n\n")
save(project_dir / "outline.md", "# Story Outline\n\n")
save(project_dir / "script.txt", "")
save(project_dir / "meta.txt", "")
save(project_dir / "shorts.md", "# Shorts Plan\n\n")
save(project_dir / "checklist.md", "# Production Checklist\n\n- [ ] Topic approved\n- [ ] Title selected\n- [ ] Thumbnail selected\n- [ ] Hook selected\n- [ ] Script ready\n- [ ] Meta ready\n")

print(f"Project created: {project_dir}")
