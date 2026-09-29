"""Data contracts for the survey/scorecard interpretation analyzer.

The tool answers one question per survey: is the organization's binary
interpretation of this survey (9-10 = PASS, 1-8 = FAIL) consistent with the
total evidence the survey itself contains (score + written comment)?

It never changes a score, and it never decides bonuses, promotions,
discipline, raises, or performance ratings. Findings are advisory and
routed to human review.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class SentimentResult:
    sentiment: str  # strongly_positive | positive | neutral | mixed | negative
    positive_hits: int
    negative_hits: int
    matched_positive: tuple = ()
    matched_negative: tuple = ()
    # Raw, auditable inputs: never reduce to the winning label alone.
    confidence: float = 0.0  # |pos-neg| / (pos+neg), 0 when no hits


@dataclass(frozen=True)
class Survey:
    survey_id: str
    branch: str
    teller: str
    score: int  # 1..10
    comment: str
    timestamp: str  # ISO-8601; scorecard impact is chronological, so required
    cohort: str = "new_way"  # "new_way" (full analyzer) | "old_way" (scorecard only)


@dataclass(frozen=True)
class TextEvidence:
    has_text: bool
    sentiment_status: str  # "available" | "unavailable"
    sentiment_label: str | None  # strongly_positive | positive | neutral | mixed | negative
    positive_themes: tuple = field(default=())
    negative_themes: tuple = field(default=())
    resolution: str = "unknown"  # "resolved" | "unresolved" | "unknown"


@dataclass(frozen=True)
class ScorecardPoint:
    """The branch scorecard around one survey, in chronological order."""
    before_pct: float | None  # None when this is the branch's first survey
    after_pct: float
    delta_pp: float | None  # after - before, percentage points
    tier_before: str | None  # "gold" | "silver" | "none"
    tier_after: str
    tier_crossed: bool  # the survey moved the branch across a bonus tier


@dataclass(frozen=True)
class InterpretationResult:
    survey_id: str
    branch: str
    teller: str
    score: int
    comment: str
    timestamp: str
    # Dimension 1: official scorecard treatment (pure function of score).
    official_treatment: str  # "PASS" | "FAIL"
    # Dimension 2: written-feedback evidence (flattened for CSV).
    has_text: bool
    sentiment_status: str
    sentiment_label: str | None
    # Interpretation of the two dimensions together.
    interpretation_status: str
    #   "score_comment_conflict" | "consistent_with_official_treatment"
    # | "insufficient_text_evidence" | "text_inconclusive" | "not_screened"
    #   ("not_screened": old_way cohort — the scorecard-only method never
    #    examines written feedback, so the conflict question is unasked.)
    # Dimension 3: scorecard impact (chronological, per branch).
    scorecard_before_pct: float | None
    scorecard_after_pct: float
    scorecard_delta_pp: float | None
    tier_before: str | None
    tier_after: str
    tier_crossed: bool
    # Two independent signals. A survey can have either, both, or neither.
    # conflict_flag ........ an interpretation problem: the scorecard's binary
    #                        treatment of the score disagrees with the written
    #                        evidence. This is what warrants human review.
    # tier_crossed .......... a scorecard-impact event: the survey moved the
    #                        branch across a bonus tier. Important, but not an
    #                        interpretation problem on its own.
    conflict_flag: bool
    needs_human_review: bool  # == conflict_flag
    reason: str
    positive_themes: tuple = field(default=())
    negative_themes: tuple = field(default=())
    resolution: str = "unknown"
    # Which method produced this row: "new_way" (full analyzer) or
    # "old_way" (scorecard only — interpretation never screened).
    cohort: str = "new_way"
    # Adjusted ("truer") scorecard view: what the branch scorecard would
    # look like if written evidence were honored (see
    # scorecard.adjusted_treatment). The official scorecard fields above
    # are never altered; this is a separate what-if view, filled by the
    # pipeline after interpretation.
    adjusted_before_pct: float | None = None
    adjusted_after_pct: float | None = None
    adjusted_delta_pp: float | None = None
    adjusted_tier_before: str | None = None
    adjusted_tier_after: str | None = None
    adjusted_tier_crossed: bool = False
