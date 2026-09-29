"""Interpretation engine: does the scorecard's treatment of a survey agree
with the survey's own written evidence?

Three independent dimensions per survey:
  1. Official scorecard treatment — PASS (9-10) / FAIL (1-8). A pure
     function of the score; the comment can never change it.
  2. Written-feedback evidence — sentiment, service themes, resolution.
  3. Scorecard impact — branch scorecard before/after, tier crossing.

Interpretation statuses:
  score_comment_conflict ......... official treatment contradicts the
                                   written evidence (either direction)
  consistent_with_official_treatment
  insufficient_text_evidence ..... blank comment: no evidence, not negative
                                   evidence — the conflict question cannot
                                   be answered
  text_inconclusive .............. neutral/mixed text: no strong signal

Advisory only. The engine never changes a score and never decides
bonuses, promotions, discipline, raises, or performance ratings.
"""

from __future__ import annotations

from .evidence import extract_evidence
from .schemas import InterpretationResult, ScorecardPoint, Survey, TextEvidence
from .scorecard import PASS_SCORE, is_pass
from .sentiment import SentimentEvidence, SentimentProvider

POSITIVE_LABELS = {"strongly_positive", "positive"}
NEGATIVE_LABELS = {"negative"}

ADVISORY_FOOTER = ("Human review recommended. This tool does not change "
                   "scores and does not decide bonuses, promotions, "
                   "discipline, raises, or performance ratings.")


def official_treatment(score: int) -> str:
    """The scorecard's binary interpretation. Comment-independent by design."""
    return "PASS" if is_pass(score) else "FAIL"


def _polarity(label: str | None) -> str:
    if label is None:
        return "unknown"
    lowered = label.lower()
    if lowered in POSITIVE_LABELS:
        return "positive"
    if lowered in NEGATIVE_LABELS:
        return "negative"
    return "neutral"


def interpret(survey: Survey, evidence: TextEvidence,
              point: ScorecardPoint) -> InterpretationResult:
    treatment = official_treatment(survey.score)
    polarity = _polarity(evidence.sentiment_label)

    if not evidence.has_text or evidence.sentiment_status != "available":
        status = "insufficient_text_evidence"
        reason = ("No usable written feedback accompanied this survey, so the "
                  f"official {treatment} treatment cannot be cross-checked "
                  "against the customer's own words. A blank comment is not "
                  "evidence of poor service.")
    elif treatment == "FAIL" and polarity == "positive" \
            and not evidence.negative_themes \
            and evidence.resolution != "unresolved":
        status = "score_comment_conflict"
        reason = (
            f"Scorecard interpretation conflict: the score of {survey.score}/10 "
            f"is officially a {treatment} — it does not count toward the branch "
            f"scorecard — but the customer's written feedback is positive "
            f"({evidence.sentiment_label}), states no service failure, and "
            f"reports the need {evidence.resolution}. Treating this survey as "
            f"evidence of poor service is not supported by the survey's own "
            f"written evidence."
        )
    elif treatment == "PASS" and polarity == "negative" and evidence.negative_themes:
        status = "score_comment_conflict"
        reason = (
            f"Scorecard interpretation conflict: the score of {survey.score}/10 "
            f"is officially a {treatment} — it counts toward the branch "
            f"scorecard — but the customer's written feedback is negative "
            f"({evidence.sentiment_label}) with stated service failures "
            f"({', '.join(evidence.negative_themes)}). Counting this survey as "
            f"evidence of good service is not supported by the survey's own "
            f"written evidence."
        )
    elif ((treatment == "FAIL" and polarity == "negative")
          or (treatment == "PASS" and polarity == "positive")):
        status = "consistent_with_official_treatment"
        reason = (
            f"The written feedback ({evidence.sentiment_label}) agrees with "
            f"the official {treatment} treatment of the {survey.score}/10 score."
        )
    else:
        status = "text_inconclusive"
        reason = (
            f"The written feedback ({evidence.sentiment_label or 'unavailable'}) "
            f"gives no strong signal either way about the official {treatment} "
            f"treatment of the {survey.score}/10 score."
        )

    # Two independent signals: an interpretation problem and a scorecard-
    # impact event are different things. A clean 10/10 that lifts a branch
    # from silver to gold crosses a tier without any conflict; only a
    # conflict warrants human review.
    conflict_flag = status == "score_comment_conflict"
    needs_human_review = conflict_flag

    if point.tier_crossed:
        reason += (f" This survey moved the branch scorecard from "
                   f"{point.before_pct}% ({point.tier_before}) to "
                   f"{point.after_pct}% ({point.tier_after}).")
    if needs_human_review:
        reason += " " + ADVISORY_FOOTER

    return InterpretationResult(
        survey_id=survey.survey_id, branch=survey.branch, teller=survey.teller,
        score=survey.score, comment=survey.comment, timestamp=survey.timestamp,
        official_treatment=treatment,
        has_text=evidence.has_text, sentiment_status=evidence.sentiment_status,
        sentiment_label=evidence.sentiment_label,
        positive_themes=evidence.positive_themes,
        negative_themes=evidence.negative_themes,
        resolution=evidence.resolution,
        interpretation_status=status,
        scorecard_before_pct=point.before_pct,
        scorecard_after_pct=point.after_pct,
        scorecard_delta_pp=point.delta_pp,
        tier_before=point.tier_before, tier_after=point.tier_after,
        tier_crossed=point.tier_crossed,
        conflict_flag=conflict_flag, needs_human_review=needs_human_review,
        reason=reason,
    )


def analyze(surveys: list[Survey],
            provider: SentimentProvider | None = None) -> list[InterpretationResult]:
    """Full pipeline: sentiment -> evidence -> running scorecard -> interpret."""
    from .sentiment import RuleBasedProvider
    from .scorecard import running_scorecard
    provider = provider or RuleBasedProvider()
    evidence_list = provider.analyze_batch([s.comment for s in surveys])
    assert len(evidence_list) == len(surveys)
    points = running_scorecard(surveys)
    results = []
    for survey, ev in zip(surveys, evidence_list):
        evidence = extract_evidence(survey.comment, ev)
        results.append(interpret(survey, evidence, points[survey.survey_id]))
    return results
