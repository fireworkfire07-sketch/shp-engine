"""Proves every scene in the production package carries a scene number,
narration, visual/video prompts, camera movement, transition, music/SFX
direction, subtitle timing and emotional/curiosity purpose — never empty,
never generic-by-omission."""

from __future__ import annotations

import unittest

from script_agent_v2 import outputs
from script_agent_v2.engines import visual_engine
from script_agent_v2.llm import LLM

SECTIONS = [
    {"name": "Açılış", "duration": "0:00-0:30", "voiceover": "Neden bu gizli sır saklandı? Cevap birazdan geliyor."},
    {"name": "Köken", "duration": "0:30-1:20", "voiceover": "1523 yılında kayıtlara geçen bu olay büyük bir gizemi saklıyordu."},
    {"name": "Final", "duration": "1:20-2:00", "voiceover": "Bugün artık biliyoruz ki bu keşif her şeyi değiştirdi."},
]

REQUIRED_STORYBOARD_KEYS = {
    "scene_number", "section", "role", "duration", "narration", "visual_idea",
    "camera_idea", "scene_idea", "transition", "music_direction",
    "sound_effect_direction", "emotional_purpose", "curiosity_purpose",
    "subtitle_start_seconds", "subtitle_end_seconds",
}


class ProductionPackageTests(unittest.TestCase):
    def setUp(self):
        plan = visual_engine.plan({})
        self.visuals = visual_engine.generate(SECTIONS, knowledge={}, visual_plan=plan, llm=LLM())

    def test_every_role_in_shot_bank_has_all_directorial_fields_non_empty(self):
        required = {"visual_idea", "camera_idea", "scene_idea", "transition", "music_direction", "sound_effect_direction", "emotional_purpose", "curiosity_purpose"}
        for role, template in visual_engine.SHOT_BANK_BY_ROLE.items():
            for key in required:
                self.assertTrue(str(template.get(key, "")).strip(), f"{role}.{key} is empty")

    def test_storyboard_has_all_required_fields_and_no_empty_strings(self):
        storyboard = outputs.build_storyboard(self.visuals, SECTIONS)
        self.assertEqual(len(storyboard), len(SECTIONS))
        for i, scene in enumerate(storyboard, start=1):
            self.assertEqual(set(scene.keys()), REQUIRED_STORYBOARD_KEYS)
            self.assertEqual(scene["scene_number"], i)
            for key, value in scene.items():
                if isinstance(value, str):
                    self.assertTrue(value.strip(), f"scene {i} field '{key}' is empty")

    def test_storyboard_subtitle_timing_is_sequential_and_non_overlapping(self):
        storyboard = outputs.build_storyboard(self.visuals, SECTIONS)
        for prev, curr in zip(storyboard, storyboard[1:]):
            self.assertLessEqual(prev["subtitle_end_seconds"], curr["subtitle_start_seconds"] + 1e-9)
        self.assertEqual(storyboard[0]["subtitle_start_seconds"], 0.0)

    def test_video_prompts_json_is_separate_from_visual_prompts_and_has_camera_and_duration(self):
        visual_prompts = outputs.build_visual_prompts(self.visuals)
        video_prompts = outputs.build_video_prompts(self.visuals, SECTIONS)
        self.assertEqual(len(video_prompts), len(SECTIONS))
        for scene in video_prompts:
            self.assertTrue(scene["video_prompt"].strip())
            self.assertTrue(scene["camera_movement"].strip())
            self.assertGreaterEqual(scene["duration_seconds"], 0)
        # genuinely distinct content, not a renamed duplicate of visual_prompts.json
        self.assertNotEqual(
            [p["prompt"] for p in visual_prompts],
            [p["video_prompt"] for p in video_prompts],
        )

    def test_video_engine_handoff_references_video_prompts_file(self):
        handoff = outputs.build_video_engine_handoff(
            {"title": "t", "sections": SECTIONS}, {}, {"decision": "APPROVE"},
        )
        self.assertEqual(handoff["video_prompts_file"], "video_prompts.json")


if __name__ == "__main__":
    unittest.main()
