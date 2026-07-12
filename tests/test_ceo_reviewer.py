"""Proves Script Agent V2's CEO Reviewer gate actually gates at 85/100,
that a genuinely strong script can clear it, and that a hard floor
violation forces REJECT even when the weighted average would pass."""

from __future__ import annotations

import unittest

from script_agent_v2.engines import ceo_reviewer


def _evaluations(curiosity=90, retention=90, emotion=90, originality=90, fact=90, first_checkpoint_risk="düşük"):
    return {
        "curiosity": {"overall_score": curiosity, "weak_sections": []},
        "retention": {
            "overall_score": retention,
            "checkpoints": [{"drop_risk": first_checkpoint_risk}, {"drop_risk": "düşük"}],
            "weak_checkpoints": [],
        },
        "emotion": {"curve_match_score": emotion, "mismatches": []},
        "originality": {"overall_score": originality, "flagged_sentences": []},
        "fact": {"overall_score": fact, "unverified_claim_count": 0},
    }


class CeoReviewerTests(unittest.TestCase):
    def test_approval_threshold_is_85(self):
        self.assertEqual(ceo_reviewer.APPROVAL_THRESHOLD, 85)

    def test_strong_specific_script_can_pass(self):
        script = {
            "title": "Bu Zehirli Bitki Neden Yüzyıllarca Gizli Tutuldu?",
            "hook": "Kimse bilmiyordu ama bu gizli sır bir imparatorluğu yıktı. Neden mi? Cevap birazdan geliyor.",
        }
        review = ceo_reviewer.review(script, _evaluations())
        self.assertGreaterEqual(
            review["ceo_score"], 85,
            f"Expected a strong script to clear 85, got {review['ceo_score']} "
            f"(components: {review['component_scores']})",
        )
        self.assertEqual(review["decision"], "APPROVE")
        self.assertEqual(review["floor_violations"], [])

    def test_generic_weak_script_is_rejected(self):
        script = {"title": "Bitkiler Hakkında Bilgiler", "hook": "Bugün bitkilerden bahsedeceğiz."}
        review = ceo_reviewer.review(script, _evaluations(curiosity=35, retention=40, emotion=30, originality=60, fact=50))
        self.assertEqual(review["decision"], "REJECT")
        self.assertLess(review["ceo_score"], 85)

    def test_hard_floor_violation_forces_reject_even_with_high_average(self):
        # originality below its hard floor (40) must reject regardless of
        # every other dimension being maxed out.
        review = ceo_reviewer.review(
            {"title": "Güçlü Başlık Örneği", "hook": "Neden bu sır saklandı?"},
            _evaluations(curiosity=100, retention=100, emotion=100, originality=20, fact=100),
        )
        self.assertEqual(review["decision"], "REJECT")
        self.assertTrue(any("Özgünlük" in reason for reason in review["floor_violations"]))

    def test_weak_first_three_seconds_forces_reject(self):
        review = ceo_reviewer.review(
            {"title": "Güçlü Başlık Örneği", "hook": "Neden bu sır saklandı?"},
            _evaluations(first_checkpoint_risk="yüksek"),
        )
        self.assertEqual(review["decision"], "REJECT")
        self.assertIn("İlk 3 saniye izleyiciyi tutmuyor.", review["floor_violations"])

    def test_never_fakes_approval_missing_keys_raises(self):
        # A malformed evaluations dict must fail loudly, never silently
        # default to an APPROVE.
        with self.assertRaises(KeyError):
            ceo_reviewer.review({"title": "x", "hook": "y"}, {})


if __name__ == "__main__":
    unittest.main()
