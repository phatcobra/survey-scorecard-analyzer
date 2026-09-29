"""Tests for the adjusted ("truer") scorecard view."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.ingest import load_surveys  # noqa: E402
from src.interpreter import analyze  # noqa: E402
from src.scorecard import adjusted_treatment, running_adjusted_scorecard  # noqa: E402


class TestAdjustedTreatment(unittest.TestCase):
    def test_conflict_flips_fail_to_pass(self):
        self.assertEqual(
            adjusted_treatment("FAIL", "score_comment_conflict"), "PASS")

    def test_conflict_flips_pass_to_fail(self):
        self.assertEqual(
            adjusted_treatment("PASS", "score_comment_conflict"), "FAIL")

    def test_no_conflict_keeps_official(self):
        for status in ("consistent_with_official_treatment",
                       "insufficient_text_evidence", "text_inconclusive",
                       "not_screened"):
            self.assertEqual(adjusted_treatment("FAIL", status), "FAIL")
            self.assertEqual(adjusted_treatment("PASS", status), "PASS")


class TestRunningAdjustedScorecard(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.results = analyze(load_surveys())
        cls.points = running_adjusted_scorecard(cls.results)
        cls.by_id = {r.survey_id: r for r in cls.results}

    def test_motivating_fixture_stays_gold_in_adjusted_view(self):
        # s_chase8: 8/10 with a great comment. Official: 95.83% gold ->
        # 92.0% silver (the 8 hurts the branch). Adjusted: stays gold.
        r = self.by_id["s_chase8"]
        self.assertEqual(r.scorecard_after_pct, 92.0)
        self.assertEqual(r.tier_after, "silver")
        p = self.points["s_chase8"]
        self.assertEqual(p.after_pct, 96.0)
        self.assertEqual(p.tier_after, "gold")
        self.assertFalse(p.tier_crossed)

    def test_reverse_conflict_counts_as_fail(self):
        # s_rev10: 10/10 with a hostile unresolved comment.
        r = self.by_id["s_rev10"]
        self.assertEqual(r.official_treatment, "PASS")
        self.assertEqual(r.interpretation_status, "score_comment_conflict")
        # In the adjusted running scorecard s_rev10 adds zero passes:
        # s_chase8 left the adjusted tally at 24/25 (flipped to pass),
        # s_rev10 leaves it at 24/26 (flipped to fail).
        prev = self.points["s_chase8"]
        cur = self.points["s_rev10"]
        self.assertEqual(round(prev.after_pct / 100 * 25), 24)
        self.assertEqual(round(cur.after_pct / 100 * 26), 24)

    def test_old_way_adjusted_equals_official(self):
        # No evidence examined -> no adjustment, ever.
        for r in self.results:
            if r.cohort != "old_way":
                continue
            p = self.points[r.survey_id]
            self.assertEqual(p.after_pct, r.scorecard_after_pct)
            self.assertEqual(p.tier_after, r.tier_after)

    def test_consistent_surveys_keep_official_treatment(self):
        # A consistent survey's own treatment is never touched. (Its running
        # adjusted % can still differ from official when an earlier conflict
        # in the same branch shifted the cumulative tally — that is correct.)
        for r in self.results:
            if r.interpretation_status != "consistent_with_official_treatment":
                continue
            self.assertEqual(
                adjusted_treatment(r.official_treatment,
                                   r.interpretation_status),
                r.official_treatment)


if __name__ == "__main__":
    unittest.main()
