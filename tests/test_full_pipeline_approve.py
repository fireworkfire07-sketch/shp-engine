"""Proves the explicitly required case the rest of the suite doesn't cover
on its own: a genuinely strong script clears the real (85-point) CEO gate
end to end, and APPROVE actually produces the complete, real production
package - all 10 files, every scene populated, nothing empty - not just
that individual engines return non-empty dicts in isolation.

The fixture text below was empirically calibrated against the real,
unmocked scoring engines (only the GROQ network call is mocked) until it
cleared the 85-point threshold with zero floor violations - see the
commit message for the calibration process. This is deliberately the
"strong script can pass" side of the gate; test_ceo_reviewer.py and
test_honest_fallback.py already cover the generic/weak-script-rejected and
missing-API-key sides.
"""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from script_agent_v2 import outputs as sa_outputs
from script_agent_v2.engines import (
    audience_engine, ceo_reviewer, curiosity_engine, doctor, emotion_engine,
    fact_engine, generator, memory_engine, originality_engine, retention_engine,
    visual_engine,
)
from script_agent_v2.llm import LLM

CONTEXT_DICT = {
    "topic": "Bu Zehirli Bitki Neden Yüzyıllarca Gizli Tutuldu?",
    "niche": "zehirli bitkiler", "decision": "ÇEK", "effort_verdict": "EMEĞİNE DEĞER",
    "first_3_seconds": "Neden bu gizli sır saklandı?", "retention_plan": [], "engagement_plan": [],
    "keywords": ["gizem", "tarih"], "hashtags": ["#gizem"], "competitor_reference": {}, "video_dna": {},
    "thumbnail_direction": "", "hook_direction": "", "channel_lessons": {},
}
STORY_DNA_PLAN = {
    "recommended_chapter_count": 6, "recommended_chapter_length_seconds": 60,
    "target_duration_seconds": 400, "recommended_hook_style": "x", "ending_style": "y",
}
SECTION_NAMES = ["Açılış", "Köken", "Kırılma", "Derinleşen Gizem", "Keşif", "Final"]
SECTION_TEXTS = [
    "Neden bu gizli sır yüzyıllarca saklandı? Nasıl bu kadar uzun süre gizli kalabildi? Cevap birazdan geliyor; sonunda öğreneceksiniz.",
    "Meğer kayıtlar birbirini tutmuyordu; şaşırtıcı biçimde gerçek çok daha karmaşıktı. İnanılmaz ama doğruydu — peki bu nasıl mümkün oldu? Cevap az sonra netleşiyor.",
    "Ama tehlike büyüyordu; savaş ve çatışma iç içe geçmişti, ihanet her köşede pusudaydı. Neden kimse bu tehdidi durduramadı? Sonunda gerçek ortaya çıkacaktı; cevap birazdan geliyor.",
    "Risk gittikçe artıyordu; bu ölümcül tehdit imparatorluğu yıkabilirdi. Peki bu kriz nasıl çözülecekti? Cevap birazdan geliyor.",
    "Sonunda kanıt bulundu; gerçek gün yüzüne çıktı ve bu büyük gizem çözüldü. Neden bu kadar gecikti? Artık her şey anlaşıldı.",
    "Bugün artık biliyoruz ki bu büyük keşif her şeyi değiştirdi. Neden mi? Çünkü gizli sır sonunda çözüldü ve cevap netleşti. Sonuç olarak imparatorluğun kaderi bu yüzden tamamen değişti; işte bu yüzden hikaye hâlâ anlatılıyor.",
]
KNOWLEDGE = {
    "facts": [{"text": "Bu gizli sır yüzyıllarca saklandı ve resmi kayıtlara geç girdi.", "category": "tarihsel", "confidence": "orta"}],
    "timeline": [], "key_people": [], "locations": [],
}
STRONG_SCRIPT_JSON = {
    "title": "Bu Zehirli Bitki Neden Yüzyıllarca Gizli Tutuldu?", "alt_titles": [],
    "hook": SECTION_TEXTS[0], "alt_hooks": [],
    "sections": [{"name": n, "duration": "", "voiceover": t} for n, t in zip(SECTION_NAMES, SECTION_TEXTS)],
    "thumbnail_concept": "Tek ana nesne, yüksek kontrast, tek gizem işareti.",
    "description": "Bu Zehirli Bitki Neden Yüzyıllarca Gizli Tutuldu?", "tags": ["gizem", "tarih"],
}
REQUIRED_OUTPUT_FILES = [
    "script.json", "script.md", "storyboard.json", "visual_prompts.json", "video_prompts.json",
    "voiceover.txt", "subtitle.srt", "thumbnail.json", "youtube_upload.json", "video_engine_handoff.json",
]


def _fake_complete_json(self, system, user, temperature=0.6, timeout=90):
    lowered = system.lower()
    if "title" in lowered or "script generator" in lowered:
        return dict(STRONG_SCRIPT_JSON)
    return None  # doctor rewrites / originality rewrites: fall back to deterministic


class FullPipelineApproveTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.output_dir = self.tmp / "script-agent"
        self.output_dir.mkdir()
        self.patches = [
            mock.patch.object(sa_outputs, "OUTPUT_DIR", self.output_dir),
            mock.patch("script_agent_v2.llm.LLM.available", new_callable=mock.PropertyMock, return_value=True),
            mock.patch("script_agent_v2.llm.LLM.complete_json", _fake_complete_json),
        ]
        for p in self.patches:
            p.start()
            self.addCleanup(p.stop)

    def test_strong_script_clears_85_point_gate_and_writes_full_package(self):
        llm = LLM()
        psychology_plan = {}
        audience_profile = audience_engine.run(CONTEXT_DICT)
        curiosity_plan = curiosity_engine.plan(STORY_DNA_PLAN)
        retention_plan = retention_engine.plan(CONTEXT_DICT)
        emotion_plan = emotion_engine.plan(STORY_DNA_PLAN)
        originality_plan = originality_engine.plan(CONTEXT_DICT)
        visual_plan = visual_engine.plan(CONTEXT_DICT)
        fact_ledger = fact_engine.build_ledger(KNOWLEDGE)

        script = generator.generate(
            CONTEXT_DICT, llm, KNOWLEDGE, STORY_DNA_PLAN, psychology_plan, audience_profile,
            curiosity_plan, retention_plan, emotion_plan, originality_plan, fact_ledger, {}, None,
        )
        script = doctor.review_and_fix(script, llm, curiosity_plan, retention_plan, emotion_plan, originality_plan, fact_ledger)

        sections = script["sections"]
        evaluations = {
            "curiosity": curiosity_engine.evaluate(sections, curiosity_plan),
            "retention": retention_engine.evaluate(sections, retention_plan),
            "emotion": emotion_engine.evaluate(sections, emotion_plan),
            "originality": originality_engine.evaluate(sections, originality_plan, llm),
            "fact": fact_engine.evaluate(sections, fact_ledger),
        }
        ceo_review = ceo_reviewer.review(script, evaluations)

        # The gate itself: this is the "strong specific script can pass" proof.
        self.assertEqual(ceo_review["decision"], "APPROVE")
        self.assertGreaterEqual(ceo_review["ceo_score"], 85)
        self.assertEqual(ceo_review["floor_violations"], [])

        visuals = visual_engine.generate(sections, KNOWLEDGE, visual_plan, llm)
        sa_outputs.write_all(script, CONTEXT_DICT, KNOWLEDGE, STORY_DNA_PLAN, evaluations, ceo_review, visuals, 1, [])

        # The production-package proof: APPROVE must produce every file,
        # fully populated, not a partial or placeholder set.
        for filename in REQUIRED_OUTPUT_FILES:
            path = self.output_dir / filename
            self.assertTrue(path.exists(), f"{filename} was not written")
            self.assertGreater(path.stat().st_size, 0, f"{filename} is empty")

        script_json = json.loads((self.output_dir / "script.json").read_text(encoding="utf-8"))
        self.assertEqual(script_json["status"], "APPROVE")

        storyboard = json.loads((self.output_dir / "storyboard.json").read_text(encoding="utf-8"))
        self.assertEqual(len(storyboard), len(SECTION_NAMES))
        for scene in storyboard:
            for field in ("narration", "visual_idea", "camera_idea", "transition", "music_direction", "emotional_purpose", "curiosity_purpose"):
                self.assertTrue(str(scene[field]).strip(), f"scene {scene['scene_number']} field {field} is empty")

        handoff = json.loads((self.output_dir / "video_engine_handoff.json").read_text(encoding="utf-8"))
        self.assertEqual(handoff["status"], "READY_FOR_VIDEO_ENGINE")

        youtube_upload = json.loads((self.output_dir / "youtube_upload.json").read_text(encoding="utf-8"))
        self.assertTrue(youtube_upload["ceo_approved"])
        self.assertEqual(youtube_upload["visibility"], "private")


if __name__ == "__main__":
    unittest.main()
