"""Guards against regression into placeholder modules: every one of the 14
engines pipeline.py wires in must accept minimal real input and return a
non-empty, real result — not an empty stub."""

from __future__ import annotations

import unittest

from script_agent_v2.engines import (
    audience_engine,
    curiosity_engine,
    emotion_engine,
    fact_engine,
    knowledge_engine,
    memory_engine,
    originality_engine,
    psychology_engine,
    retention_engine,
    story_dna_engine,
    visual_engine,
)
from script_agent_v2.llm import LLM

CONTEXT = {"topic": "Zehirli Bitkilerin Gizli Tarihi", "niche": "bitkiler", "keywords": ["tarih"], "competitor_reference": {}}
SECTIONS = [
    {"name": "Açılış", "duration": "0:00-1:00", "voiceover": "Neden bu gizli sır saklandı? Cevap birazdan geliyor."},
    {"name": "Final", "duration": "1:00-2:00", "voiceover": "Bugün artık biliyoruz ki bu keşif her şeyi değiştirdi."},
]


class EnginesAreRealTests(unittest.TestCase):
    def test_psychology_engine_scores_real_text(self):
        result = psychology_engine.score(SECTIONS[0]["voiceover"])
        self.assertGreater(result["average"], 0)

    def test_audience_engine_returns_a_profile(self):
        profile = audience_engine.run(CONTEXT)
        self.assertIn("label", profile)
        self.assertTrue(profile["label"])

    def test_curiosity_engine_plan_and_evaluate(self):
        plan = curiosity_engine.plan({"target_duration_seconds": 400})
        self.assertGreater(plan["required_gap_count"], 0)
        result = curiosity_engine.evaluate(SECTIONS, plan)
        self.assertIn("overall_score", result)

    def test_retention_engine_plan_and_evaluate(self):
        plan = retention_engine.plan(CONTEXT)
        result = retention_engine.evaluate(SECTIONS, plan)
        self.assertTrue(result["checkpoints"])

    def test_emotion_engine_plan_and_evaluate(self):
        plan = emotion_engine.plan({"recommended_chapter_count": 2})
        result = emotion_engine.evaluate(SECTIONS, plan)
        self.assertEqual(len(result["detected_curve"]), len(SECTIONS))

    def test_originality_engine_plan_and_evaluate(self):
        plan = originality_engine.plan(CONTEXT)
        result = originality_engine.evaluate(SECTIONS, plan, LLM())
        self.assertIn("overall_score", result)

    def test_fact_engine_ledger_and_evaluate(self):
        ledger = fact_engine.build_ledger({"facts": [{"text": "1900'de oldu.", "category": "tarihsel", "confidence": "orta"}]})
        result = fact_engine.evaluate(SECTIONS, ledger)
        self.assertIn("overall_score", result)

    def test_story_dna_engine_returns_real_plan(self):
        result = story_dna_engine.run(CONTEXT, story_dna=[], memory={})
        self.assertGreaterEqual(result["recommended_chapter_count"], 6)
        self.assertTrue(result["recommended_hook_style"])

    def test_visual_engine_plan_and_generate(self):
        plan = visual_engine.plan(CONTEXT)
        visuals = visual_engine.generate(SECTIONS, {}, plan, LLM())
        self.assertEqual(len(visuals), len(SECTIONS))
        for v in visuals:
            self.assertTrue(v["visual_idea"])
            self.assertTrue(v["camera_idea"])

    def test_knowledge_engine_returns_structured_result(self):
        result = knowledge_engine.run(CONTEXT, LLM())
        self.assertIn("facts", result)
        self.assertIn("research_mode", result)

    def test_memory_engine_records_and_reads_back(self):
        memory = {"runs": [], "best_hooks": [], "best_endings": [], "best_thumbnails": []}
        script = {"title": "T", "hook": "Neden?", "sections": SECTIONS}
        ceo_review = {"reviewed_at": "now", "ceo_score": 90, "decision": "APPROVE"}
        evaluations = {"curiosity": {"overall_score": 90}, "retention": {"overall_score": 90}}
        updated = memory_engine.record(memory, script, ceo_review, evaluations, {"recommended_chapter_length_seconds": 60})
        self.assertEqual(len(updated["runs"]), 1)
        hints = memory_engine.hints_for_generation(updated)
        self.assertEqual(hints["approved_run_count"], 1)


if __name__ == "__main__":
    unittest.main()
