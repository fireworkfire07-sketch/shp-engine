"""SHP Script Agent V2 — autonomous Head Writer AI entrypoint.

Runs the full 14-engine pipeline (script_agent_v2/pipeline.py) and writes
script.md, script.json, storyboard.json, visual_prompts.json, voiceover.txt,
subtitle.srt, thumbnail.json, youtube_upload.json and video_engine_handoff.json
to projects/script-agent/.

Script Agent V1 (script_agent.py) is untouched and still runnable directly.
"""

from __future__ import annotations

from script_agent_v2.pipeline import run

if __name__ == "__main__":
    run()
