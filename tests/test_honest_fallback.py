"""Proves Script Agent V2 engines never invent facts or fake confidence
when none of GEMINI_API_KEY/OPENAI_API_KEY/GROQ_API_KEY is available — they
must mark themselves as rule_based_fallback / low-confidence instead of
guessing."""

from __future__ import annotations

import unittest
from unittest import mock

from script_agent_v2.engines import generator, knowledge_engine
from script_agent_v2.llm import LLM


class HonestFallbackTests(unittest.TestCase):
    def setUp(self):
        self._env_patch = mock.patch.dict(
            "os.environ", {"GEMINI_API_KEY": "", "OPENAI_API_KEY": "", "GROQ_API_KEY": ""}, clear=False
        )
        self._env_patch.start()
        self.addCleanup(self._env_patch.stop)

    def test_llm_reports_unavailable_without_key(self):
        self.assertFalse(LLM().available)

    def test_knowledge_engine_never_invents_facts_without_key(self):
        result = knowledge_engine.run({"topic": "Bilinmeyen Bir Bitki", "niche": "test"}, LLM())
        self.assertEqual(result["research_mode"], "rule_based_fallback")
        self.assertIn("GROQ_API_KEY", result["research_note"])
        for fact in result["facts"]:
            self.assertEqual(fact["confidence"], "düşük")

    def test_generator_fallback_produces_valid_structure_without_key(self):
        context_dict = {"topic": "Test Konusu", "keywords": [], "thumbnail_direction": ""}
        story_dna_plan = {"recommended_chapter_count": 6, "recommended_chapter_length_seconds": 60}
        script = generator.generate(
            context_dict, LLM(), knowledge={}, story_dna_plan=story_dna_plan,
            psychology_plan={}, audience_profile={}, curiosity_plan={}, retention_plan={},
            emotion_plan={}, originality_plan={}, fact_ledger=[], memory_hints={}, feedback=None,
        )
        self.assertEqual(script["source_mode"], "rule_based_fallback")
        self.assertTrue(script["title"])
        self.assertTrue(script["hook"])
        self.assertGreaterEqual(len(script["sections"]), 5)
        for section in script["sections"]:
            self.assertTrue(section["voiceover"].strip())

    def test_pipeline_never_crashes_without_any_api_keys(self):
        # generate -> doctor -> evaluate must all complete without an LLM.
        from script_agent_v2.engines import ceo_reviewer, curiosity_engine, doctor, emotion_engine, fact_engine, originality_engine

        context_dict = {"topic": "Test Konusu", "keywords": [], "thumbnail_direction": "", "competitor_reference": {}}
        story_dna_plan = {"recommended_chapter_count": 6, "recommended_chapter_length_seconds": 60}
        llm = LLM()
        script = generator.generate(
            context_dict, llm, knowledge={}, story_dna_plan=story_dna_plan,
            psychology_plan={}, audience_profile={}, curiosity_plan={"minimum_section_score": 45},
            retention_plan={}, emotion_plan={"target_curve": []}, originality_plan={"avoid_corpus": []},
            fact_ledger=[], memory_hints={}, feedback=None,
        )
        script = doctor.review_and_fix(script, llm, {"minimum_section_score": 45}, {}, {"target_curve": []}, {"avoid_corpus": []}, [])
        sections = script["sections"]
        evaluations = {
            "curiosity": curiosity_engine.evaluate(sections, {"minimum_section_score": 45}),
            "retention": {"overall_score": 50, "checkpoints": [{"drop_risk": "orta"}], "weak_checkpoints": []},
            "emotion": emotion_engine.evaluate(sections, {"target_curve": []}),
            "originality": originality_engine.evaluate(sections, {"avoid_corpus": []}, llm),
            "fact": fact_engine.evaluate(sections, []),
        }
        review = ceo_reviewer.review(script, evaluations)
        self.assertIn(review["decision"], {"APPROVE", "REJECT"})


if __name__ == "__main__":
    unittest.main()
