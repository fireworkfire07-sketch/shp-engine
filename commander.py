from pathlib import Path
import json

PROJECT = Path("project")
PROJECT.mkdir(exist_ok=True)

def save(name, content):
    (PROJECT / name).write_text(content, encoding="utf-8")

topic = input("Topic: ")

analysis = {
    "topic": topic,
    "status": "pending",
    "score": 0
}

save("analysis.json", json.dumps(analysis, indent=2))
save("titles.md", "")
save("thumbnail.md", "")
save("hook.md", "")
save("outline.md", "")
save("script.txt", "")
save("meta.txt", "")

print("Project created.")
