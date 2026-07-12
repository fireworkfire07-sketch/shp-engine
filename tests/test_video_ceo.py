"""Proves Video CEO Pro actually gates the finished production package:
blocks on missing data, blocks on policy risk regardless of score, sends
real corrections back through the real Script Agent V2 engines on DÜZELT
(mocking only the GROQ network call, nothing else), and never DÜZELTs a
rule_based_fallback script it cannot honestly improve."""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import video_ceo

STRONG_SECTIONS = [
    {"name": "Açılış", "duration": "0:00-0:30", "voiceover": "Kimse bilmiyordu ama bu gizli sır bir imparatorluğu yıktı. Neden mi? Cevap birazdan geliyor."},
    {"name": "Köken", "duration": "0:30-1:20", "voiceover": "1523 yılında kayıtlara geçen bu olay, tarihçilerin uzun süre gözden kaçırdığı bir ayrıntıyı gizliyordu."},
    {"name": "Kırılma", "duration": "1:20-2:10", "voiceover": "Ama asıl gerçek çok daha karanlıktı; savaş ve ihanet iç içe geçmişti."},
    {"name": "Derinleşen Gizem", "duration": "2:10-3:00", "voiceover": "Şaşırtıcı biçimde, kayıtlar birbirini tutmuyordu; meğer resmi anlatı eksikti."},
    {"name": "Keşif", "duration": "3:00-3:50", "voiceover": "Sonunda araştırmacılar kanıt buldu; gün yüzüne çıkan belgeler her şeyi değiştirdi."},
    {"name": "Final", "duration": "3:50-4:30", "voiceover": "Bugün artık biliyoruz ki bu keşif, imparatorluğun kaderini kalıcı biçimde değiştirdi."},
]


def _strong_script_payload(source_mode="groq", status="APPROVE", ceo_score=90):
    evaluations = {
        "curiosity": {"overall_score": 90, "weak_sections": []},
        "retention": {
            "overall_score": 90,
            "checkpoints": [
                {"checkpoint_seconds": 3, "drop_risk": "düşük"},
                {"checkpoint_seconds": 10, "drop_risk": "düşük"},
                {"checkpoint_seconds": 30, "drop_risk": "düşük"},
                {"checkpoint_seconds": 60, "drop_risk": "düşük"},
                {"checkpoint_seconds": 180, "drop_risk": "düşük"},
            ],
            "weak_checkpoints": [],
        },
        "emotion": {"curve_match_score": 90, "mismatches": []},
        "originality": {"overall_score": 90, "flagged_sentences": []},
        "fact": {"overall_score": 90, "unverified_claim_count": 0},
    }
    return {
        "agent": "SHP Script Agent V2",
        "status": status,
        "attempts": 1,
        "context": {"topic": "Zehirli Bitkilerin Gizli Tarihi", "niche": "bitkiler", "keywords": ["gizem"], "competitor_reference": {}, "thumbnail_direction": ""},
        "knowledge": {"facts": [{"text": "1523 yılında kayıtlara geçti.", "category": "tarihsel", "confidence": "orta"}]},
        "story_dna_plan": {"recommended_chapter_count": 6, "recommended_chapter_length_seconds": 60, "target_duration_seconds": 400},
        "script": {
            "title": "Bu Zehirli Bitki Neden Yüzyıllarca Gizli Tutuldu?",
            "hook": STRONG_SECTIONS[0]["voiceover"],
            "sections": STRONG_SECTIONS,
            "thumbnail_concept": "Tek ana nesne, yüksek kontrast, tek gizem işareti.",
            "description": "Bu Zehirli Bitki Neden Yüzyıllarca Gizli Tutuldu?",
            "tags": ["gizem", "tarih"],
            "source_mode": source_mode,
        },
        "evaluations": evaluations,
        "ceo_review": {"decision": status, "ceo_score": ceo_score},
        "rejected_history": [],
    }


def _ceo_decision(niche_score=80, channel_fit_score=90, effort_value_score=75):
    return {"niche_score": niche_score, "channel_fit_score": channel_fit_score, "effort_value_score": effort_value_score}


class VideoCeoPureFunctionTests(unittest.TestCase):
    def test_scan_policy_risk_detects_hit(self):
        script = {"title": "x", "hook": "Bu videoda silah yapımı anlatılacak", "sections": []}
        hits = video_ceo.scan_policy_risk(script, {"description": ""})
        self.assertIn("silah yapımı", hits)

    def test_scan_policy_risk_clean_text_no_hit(self):
        script = {"title": "Bitkilerin Gizli Tarihi", "hook": "Neden bu sır saklandı?", "sections": []}
        hits = video_ceo.scan_policy_risk(script, {"description": ""})
        self.assertEqual(hits, [])

    def test_evaluate_production_package_strong_input_scores_high(self):
        payload = _strong_script_payload()
        evaluation = video_ceo.evaluate_production_package(
            payload, _ceo_decision(), niche={"winner": {"metrics": {"evergreen_score": 70}}}, growth={"trending_keywords": []},
            thumbnail={"concept": "x", "originality_risk": False}, storyboard=[{"visual_idea": "a", "camera_idea": "b", "scene_idea": "c"}],
            youtube_upload={"title": "x", "description": "y", "tags": []}, handoff={"target_duration_minutes": 5},
        )
        self.assertGreaterEqual(evaluation["video_ceo_score"], 80)
        self.assertEqual(evaluation["policy_risk_hits"], [])

    def test_build_corrections_nonempty_for_weak_dimensions(self):
        payload = _strong_script_payload()
        payload["evaluations"]["retention"]["overall_score"] = 20
        payload["evaluations"]["retention"]["checkpoints"][0]["drop_risk"] = "yüksek"
        evaluation = video_ceo.evaluate_production_package(
            payload, _ceo_decision(), niche={}, growth={}, thumbnail={"concept": ""}, storyboard=[],
            youtube_upload={"title": "x", "description": "y", "tags": []}, handoff={},
        )
        corrections = video_ceo.build_corrections(evaluation)
        self.assertTrue(any("İlk 3 saniye" in c or "İzlenme süresi" in c for c in corrections))


class VideoCeoMainFlowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.projects = self.tmp / "projects"
        self.projects.mkdir()
        self.root_patch = mock.patch.object(video_ceo, "ROOT", self.projects)
        self.output_patch = mock.patch.object(video_ceo, "OUTPUT_DIR", self.projects / "video-ceo")
        self.root_patch.start()
        self.output_patch.start()
        (self.projects / "video-ceo").mkdir()
        self.addCleanup(self.root_patch.stop)
        self.addCleanup(self.output_patch.stop)

    def _write(self, relpath: str, data) -> None:
        path = self.projects / relpath
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    def test_missing_data_returns_beklet(self):
        video_ceo.main()
        analysis = json.loads((self.projects / "video-ceo" / "analysis.json").read_text(encoding="utf-8"))
        self.assertEqual(analysis["decision"], "BEKLET — VERİ EKSİK")

    def test_strong_approved_package_returns_cek(self):
        self._write("script-agent/script.json", _strong_script_payload())
        self._write("ceo-decision/analysis.json", _ceo_decision())
        self._write("niche-intelligence/analysis.json", {"winner": {"metrics": {"evergreen_score": 70}}})
        self._write("growth-advisor/analysis.json", {"trending_keywords": []})
        self._write("script-agent/thumbnail.json", {"concept": "Tek nesne, yüksek kontrast.", "originality_risk": False})
        self._write("script-agent/storyboard.json", [{"visual_idea": "a", "camera_idea": "b", "scene_idea": "c"}] * 6)
        self._write("script-agent/youtube_upload.json", {"title": "x", "description": "y", "tags": []})
        self._write("script-agent/video_engine_handoff.json", {"target_duration_minutes": 5})

        video_ceo.main()
        analysis = json.loads((self.projects / "video-ceo" / "analysis.json").read_text(encoding="utf-8"))
        self.assertEqual(analysis["decision"], "ÇEK")
        self.assertGreaterEqual(analysis["video_ceo_score"], 80)

    def test_policy_risk_forces_dur_even_with_strong_scores(self):
        payload = _strong_script_payload()
        payload["script"]["hook"] = "Bu videoda bomba yapımı anlatılacak. " + payload["script"]["hook"]
        self._write("script-agent/script.json", payload)
        self._write("ceo-decision/analysis.json", _ceo_decision())
        self._write("niche-intelligence/analysis.json", {"winner": {"metrics": {"evergreen_score": 70}}})
        self._write("growth-advisor/analysis.json", {"trending_keywords": []})
        self._write("script-agent/thumbnail.json", {"concept": "x", "originality_risk": False})
        self._write("script-agent/storyboard.json", [{"visual_idea": "a", "camera_idea": "b", "scene_idea": "c"}] * 6)
        self._write("script-agent/youtube_upload.json", {"title": "x", "description": "y", "tags": []})
        self._write("script-agent/video_engine_handoff.json", {"target_duration_minutes": 5})

        video_ceo.main()
        analysis = json.loads((self.projects / "video-ceo" / "analysis.json").read_text(encoding="utf-8"))
        self.assertEqual(analysis["decision"], "DUR")
        self.assertTrue(analysis["policy_risk_hits"])

    def test_rule_based_fallback_never_gets_a_fake_duzelt(self):
        payload = _strong_script_payload(source_mode="rule_based_fallback", status="REJECT", ceo_score=60)
        payload["evaluations"]["retention"]["overall_score"] = 40  # push into the DÜZELT score band
        self._write("script-agent/script.json", payload)
        self._write("ceo-decision/analysis.json", _ceo_decision(niche_score=40, channel_fit_score=60, effort_value_score=40))
        self._write("niche-intelligence/analysis.json", {})
        self._write("growth-advisor/analysis.json", {})
        self._write("script-agent/thumbnail.json", {"concept": "x"})
        self._write("script-agent/storyboard.json", [{"visual_idea": "a", "camera_idea": "b", "scene_idea": "c"}] * 6)
        self._write("script-agent/youtube_upload.json", {"title": "x", "description": "y", "tags": []})
        self._write("script-agent/video_engine_handoff.json", {"target_duration_minutes": 5})

        video_ceo.main()
        analysis = json.loads((self.projects / "video-ceo" / "analysis.json").read_text(encoding="utf-8"))
        self.assertIn(analysis["decision"], {"DUR", "BEKLET — VERİ EKSİK"})
        self.assertFalse(analysis["rewrite_cycle_used"])
        self.assertTrue(any("GROQ_API_KEY" in reason for reason in analysis["reasons"]))

    def test_duzelt_runs_real_rewrite_cycle_with_mocked_groq(self):
        # Weak-but-not-policy-blocked GROQ-mode script -> DÜZELT band.
        payload = _strong_script_payload(source_mode="groq", status="REJECT", ceo_score=60)
        payload["evaluations"]["retention"]["overall_score"] = 40
        payload["evaluations"]["retention"]["checkpoints"][0]["drop_risk"] = "yüksek"
        self._write("script-agent/script.json", payload)
        self._write("ceo-decision/analysis.json", _ceo_decision(niche_score=70, channel_fit_score=80, effort_value_score=70))
        self._write("niche-intelligence/analysis.json", {"winner": {"metrics": {"evergreen_score": 60}}})
        self._write("growth-advisor/analysis.json", {"trending_keywords": []})
        self._write("script-agent/thumbnail.json", {"concept": "x", "originality_risk": False})
        self._write("script-agent/storyboard.json", [{"visual_idea": "a", "camera_idea": "b", "scene_idea": "c"}] * 6)
        self._write("script-agent/youtube_upload.json", {"title": "x", "description": "y", "tags": []})
        self._write("script-agent/video_engine_handoff.json", {"target_duration_minutes": 5})
        self._write("script-agent/memory.json", {"runs": [], "best_hooks": [], "best_endings": [], "best_thumbnails": []})

        rewritten_script = {
            "title": "Bu Zehirli Bitki Neden Yüzyıllarca Gizli Tutuldu?",
            "alt_titles": [], "hook": "Kimse bilmiyordu ama bu gizli sır bir imparatorluğu yıktı. Cevap birazdan geliyor.",
            "alt_hooks": [], "sections": STRONG_SECTIONS,
            "thumbnail_concept": "Tek nesne, yüksek kontrast.", "description": "d", "tags": ["gizem"],
        }

        def fake_complete_json(self, system, user, temperature=0.6, timeout=90):
            if "voiceover" in system.lower() or "rewrite" in system.lower():
                return None  # let doctor's deterministic fallback handle section rewrites
            return dict(rewritten_script)

        # run_rewrite_cycle re-drives the real script_agent_v2 engines, which
        # write to script_agent_v2.context/outputs' own module-level path
        # constants (bound at import time) — not video_ceo.ROOT. Sandbox
        # those too, or this test would overwrite the real committed
        # projects/script-agent/ files on disk.
        with mock.patch("script_agent_v2.llm.LLM.available", new_callable=mock.PropertyMock, return_value=True), \
             mock.patch("script_agent_v2.llm.LLM.complete_json", fake_complete_json), \
             mock.patch("script_agent_v2.context.MEMORY_PATH", self.projects / "script-agent" / "memory.json"), \
             mock.patch("script_agent_v2.outputs.OUTPUT_DIR", self.projects / "script-agent"):
            video_ceo.main()

        analysis = json.loads((self.projects / "video-ceo" / "analysis.json").read_text(encoding="utf-8"))
        self.assertTrue(analysis["rewrite_cycle_used"])
        self.assertIn(analysis["decision"], {"ÇEK", "DUR"})  # never DÜZELT again after the one cycle
        new_script = json.loads((self.projects / "script-agent" / "script.json").read_text(encoding="utf-8"))
        self.assertEqual(new_script["attempts"], payload["attempts"] + 1)
        self.assertEqual(len(new_script["rejected_history"]), 1)
        self.assertIn("reasons", new_script["rejected_history"][0])
        self.assertIn("ceo_score", new_script["rejected_history"][0])


if __name__ == "__main__":
    unittest.main()
