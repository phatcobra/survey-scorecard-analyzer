"""Conflict-detection tests: the scorecard's binary interpretation vs the
survey's own written evidence.

The central case: an 8/10 officially FAILs while the comment describes
excellent, resolved service -> score_comment_conflict. The reverse (a 10
with a negative, unresolved comment) is the same kind of conflict.
"""

import os
import sys
import unittest
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.evidence import extract_evidence  # noqa: E402
from src.interpreter import analyze, interpret, official_treatment  # noqa: E402
from src.schemas import Survey  # noqa: E402
from src.scorecard import running_scorecard  # noqa: E402
from src.sentiment import RuleBasedProvider  # noqa: E402

T0 = datetime(2026, 1, 1)
PROVIDER = RuleBasedProvider()


def S(sid, score, comment, day=0, branch="b"):
    return Survey(survey_id=sid, branch=branch, teller="t1", score=score,
                  comment=comment,
                  timestamp=(T0 + timedelta(days=day)).isoformat(timespec="seconds"))


def interpret_one(survey):
    ev = extract_evidence(survey.comment, PROVIDER.analyze_batch([survey.comment])[0])
    point = running_scorecard([survey])[survey.survey_id]
    return interpret(survey, ev, point)


class TestMotivatingCase(unittest.TestCase):
    def test_eight_with_excellent_resolved_comment_is_conflict(self):
        r = interpret_one(S("x", 8, "Excellent service and took care of all my needs."))
        self.assertEqual(r.official_treatment, "FAIL")
        self.assertEqual(r.interpretation_status, "score_comment_conflict")
        self.assertEqual(r.resolution, "resolved")
        self.assertEqual(r.positive_themes != (), True)
        self.assertEqual(r.negative_themes, ())
        self.assertTrue(r.needs_human_review)
        self.assertTrue(r.conflict_flag)
        # Advisory only: names human review, never a score change.
        self.assertIn("Human review recommended", r.reason)
        self.assertNotIn("change the 8", r.reason.lower())

    def test_reverse_conflict_ten_with_terrible_comment(self):
        r = interpret_one(S("x", 10, "Terrible experience, rude teller, they did not help with my issue at all."))
        self.assertEqual(r.official_treatment, "PASS")
        self.assertEqual(r.interpretation_status, "score_comment_conflict")
        self.assertTrue(r.needs_human_review)
        self.assertTrue(r.conflict_flag)

    def test_consistent_fail(self):
        r = interpret_one(S("x", 2, "Nobody helped me, I am still waiting for a callback."))
        self.assertEqual(r.interpretation_status, "consistent_with_official_treatment")
        self.assertFalse(r.needs_human_review)
        self.assertFalse(r.conflict_flag)

    def test_consistent_pass(self):
        r = interpret_one(S("x", 10, "Great service, quick and professional, very satisfied."))
        self.assertEqual(r.interpretation_status, "consistent_with_official_treatment")
        self.assertFalse(r.needs_human_review)
        self.assertFalse(r.conflict_flag)

    def test_blank_comment_is_not_evidence(self):
        r = interpret_one(S("x", 8, ""))
        self.assertEqual(r.interpretation_status, "insufficient_text_evidence")
        # A blank comment must never manufacture a conflict.
        self.assertNotEqual(r.interpretation_status, "score_comment_conflict")

    def test_whitespace_comment_is_not_evidence(self):
        r = interpret_one(S("x", 8, "   "))
        self.assertEqual(r.interpretation_status, "insufficient_text_evidence")

    def test_official_treatment_never_depends_on_comment(self):
        # Same score, wildly different comments -> identical treatment.
        comments = ["Excellent service and took care of all my needs.",
                    "Terrible experience, rude teller.",
                    "", "   "]
        treatments = {official_treatment(8) for _ in comments}
        self.assertEqual(treatments, {"FAIL"})
        self.assertEqual({official_treatment(9) for _ in comments}, {"PASS"})


class TestTierCrossingFlag(unittest.TestCase):
    def test_conflict_plus_tier_crossing_names_both(self):
        surveys = [S(f"p{i}", 10 if i else 7, "Great.", day=i) for i in range(24)]
        surveys.append(S("x", 8, "Excellent service and took care of all my needs.", day=24))
        by_id = {r.survey_id: r for r in analyze(surveys)}
        x = by_id["x"]
        self.assertTrue(x.tier_crossed)
        self.assertEqual((x.tier_before, x.tier_after), ("gold", "silver"))
        self.assertEqual(x.interpretation_status, "score_comment_conflict")
        self.assertTrue(x.needs_human_review)
        self.assertTrue(x.conflict_flag)
        self.assertIn("95.83%", x.reason)
        self.assertIn("92.0%", x.reason)


class TestSignalSeparation(unittest.TestCase):
    def test_clean_ten_crossing_up_is_not_a_conflict(self):
        # A perfectly normal 10/10 that lifts the branch silver -> gold:
        # tier_crossed is True, but there is no interpretation problem.
        # Build exactly: 19 surveys, 18 pass -> 94.74% (silver); then a 10
        # -> 19/20 = 95.0% (gold).
        surveys = [S(f"p{i}", 10, "Great.", day=i) for i in range(18)]
        surveys.append(S("f", 7, "It was fine.", day=18))   # 18/19 = 94.74% silver
        surveys.append(S("x", 10, "Great service, quick and professional.", day=19))
        by_id = {r.survey_id: r for r in analyze(surveys)}
        x = by_id["x"]
        self.assertTrue(x.tier_crossed)
        self.assertEqual((x.tier_before, x.tier_after), ("silver", "gold"))
        self.assertFalse(x.conflict_flag)
        self.assertFalse(x.needs_human_review)
        self.assertNotIn("Human review recommended", x.reason)
        # ...but the tier movement is still reported factually.
        self.assertIn("94.74%", x.reason)
        self.assertIn("95.0%", x.reason)

    def test_conflict_reason_carries_advisory_footer(self):
        r = interpret_one(S("x", 8, "Excellent service and took care of all my needs."))
        self.assertTrue(r.needs_human_review)
        self.assertIn("Human review recommended", r.reason)
        self.assertIn("does not decide bonuses", r.reason)

    def test_sentiment_cannot_move_score_or_scorecard(self):
        # The honest contract: official treatment and scorecard math are
        # identical whether sentiment is available or not.
        from src.sentiment import SentimentEvidence, SentimentProvider

        class NullProvider(SentimentProvider):
            def analyze_batch(self, texts):
                return [SentimentEvidence(status="unavailable", label=None,
                                          positive=None, negative=None,
                                          neutral=None, mixed=None)
                        for _ in texts]

        surveys = [S(f"s{i}", score, comment, day=i) for i, (score, comment) in
                   enumerate([(10, "Great."), (8, "Excellent service."),
                              (2, "Terrible."), (9, "")])]
        with_rules = {r.survey_id: r for r in analyze(surveys)}
        without = {r.survey_id: r for r in analyze(surveys, provider=NullProvider())}
        for sid in with_rules:
            a, b = with_rules[sid], without[sid]
            self.assertEqual(a.official_treatment, b.official_treatment)
            self.assertEqual(a.scorecard_before_pct, b.scorecard_before_pct)
            self.assertEqual(a.scorecard_after_pct, b.scorecard_after_pct)
            self.assertEqual(a.scorecard_delta_pp, b.scorecard_delta_pp)
            self.assertEqual(a.tier_before, b.tier_before)
            self.assertEqual(a.tier_after, b.tier_after)
            self.assertEqual(a.tier_crossed, b.tier_crossed)
            self.assertEqual(a.score, b.score)  # the score itself is untouched


if __name__ == "__main__":
    unittest.main()
