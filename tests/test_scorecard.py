"""Scorecard math tests: top-2-box, tiers, running impact, tier crossings.

The scorecard is % of surveys scoring 9-10. These tests pin the threshold
cliff (8 vs 9), the tier boundaries, and the per-survey marginal impact
that makes small-N scorecards so sensitive.
"""

import os
import sys
import unittest
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.schemas import Survey  # noqa: E402
from src.scorecard import (  # noqa: E402
    PASS_SCORE, bonus_for, is_pass, running_scorecard, scorecard_pct, tier_for,
)

T0 = datetime(2026, 1, 1)


def S(sid, branch, score, day):
    return Survey(survey_id=sid, branch=branch, teller="t1", score=score,
                  comment="ok", timestamp=(T0 + timedelta(days=day)).isoformat())


class TestThresholdCliff(unittest.TestCase):
    def test_nine_passes_eight_fails(self):
        # One point apart, opposite organizational meaning: the cliff.
        self.assertTrue(is_pass(9))
        self.assertTrue(is_pass(10))
        self.assertFalse(is_pass(8))
        self.assertFalse(is_pass(1))
        self.assertEqual(PASS_SCORE, 9)

    def test_official_treatment_is_score_only(self):
        from src.interpreter import official_treatment
        # The comment can never change the official treatment.
        for score in range(1, 11):
            expected = "PASS" if score >= 9 else "FAIL"
            self.assertEqual(official_treatment(score), expected)


class TestTiers(unittest.TestCase):
    def test_tier_boundaries(self):
        self.assertEqual(tier_for(100.0), "gold")
        self.assertEqual(tier_for(95.0), "gold")
        self.assertEqual(tier_for(94.99), "silver")
        self.assertEqual(tier_for(90.0), "silver")
        self.assertEqual(tier_for(89.99), "none")
        self.assertEqual(tier_for(0.0), "none")
        self.assertIsNone(tier_for(None))

    def test_bonus_amounts(self):
        self.assertEqual(bonus_for("gold"), 300)
        self.assertEqual(bonus_for("silver"), 150)
        self.assertEqual(bonus_for("none"), 0)


class TestRunningScorecard(unittest.TestCase):
    def test_before_after_delta(self):
        surveys = [S("a", "b", 9, 0), S("b", "b", 8, 1), S("c", "b", 10, 2)]
        pts = running_scorecard(surveys)
        self.assertIsNone(pts["a"].before_pct)  # first survey: no "before"
        self.assertEqual(pts["a"].after_pct, 100.0)
        self.assertEqual(pts["b"].before_pct, 100.0)
        self.assertEqual(pts["b"].after_pct, 50.0)
        self.assertEqual(pts["b"].delta_pp, -50.0)
        self.assertEqual(pts["c"].before_pct, 50.0)
        self.assertEqual(pts["c"].after_pct, 66.67)

    def test_single_survey_can_move_tiers(self):
        # 24 surveys at 95.83% (gold); one 8 -> 92.0% (silver).
        surveys = [S(f"p{i}", "b", 10 if i else 7, i) for i in range(24)]
        surveys.append(S("x", "b", 8, 24))
        pts = running_scorecard(surveys)
        x = pts["x"]
        self.assertEqual(x.before_pct, 95.83)
        self.assertEqual(x.tier_before, "gold")
        self.assertEqual(x.after_pct, 92.0)
        self.assertEqual(x.tier_after, "silver")
        self.assertTrue(x.tier_crossed)

    def test_first_survey_is_not_a_crossing(self):
        pts = running_scorecard([S("a", "b", 10, 0)])
        self.assertFalse(pts["a"].tier_crossed)
        self.assertIsNone(pts["a"].tier_before)
        self.assertEqual(pts["a"].tier_after, "gold")

    def test_input_order_does_not_matter(self):
        surveys = [S("a", "b", 9, 0), S("b", "b", 8, 1), S("c", "b", 10, 2)]
        ref = running_scorecard(surveys)
        got = running_scorecard(list(reversed(surveys)))
        self.assertEqual(ref, got)

    def test_branches_are_independent(self):
        surveys = [S("a", "b1", 10, 0), S("b", "b2", 1, 0)]
        pts = running_scorecard(surveys)
        self.assertEqual(pts["a"].after_pct, 100.0)
        self.assertEqual(pts["b"].after_pct, 0.0)

    def test_scorecard_pct_empty(self):
        self.assertIsNone(scorecard_pct(0, 0))


if __name__ == "__main__":
    unittest.main()
