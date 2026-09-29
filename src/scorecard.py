"""Branch scorecard math.

The scorecard is a top-2-box percentage: the share of surveys scoring 9 or
10. That single design choice is the whole story — a 9-10 "passes" and an
1-8 "fails", so one point of customer scoring behavior (8 vs 9) flips the
organizational meaning entirely, and with a small survey count a single
response can move the branch across a bonus tier.

Assumptions are explicit and configurable, not hidden:
  PASS_SCORE = 9 ............ scores >= 9 count toward the scorecard
  TIERS ..................... (name, minimum pct, per-person bonus $)
"""

from __future__ import annotations

from .schemas import ScorecardPoint, Survey

# --- Scorecard policy (explicit, configurable, not a universal truth) ---
PASS_SCORE = 9
TIERS: tuple[tuple[str, float, int], ...] = (
    ("gold", 95.0, 300),
    ("silver", 90.0, 150),
)
# ------------------------------------------------------------------------


def is_pass(score: int) -> bool:
    """Official scorecard treatment: a pure function of the score."""
    return score >= PASS_SCORE


def tier_for(pct: float | None) -> str | None:
    """Bonus tier for a scorecard percentage. None = no surveys yet."""
    if pct is None:
        return None
    for name, minimum, _bonus in TIERS:
        if pct >= minimum:
            return name
    return "none"


def bonus_for(tier: str | None) -> int:
    for name, _minimum, bonus in TIERS:
        if name == tier:
            return bonus
    return 0


def adjusted_treatment(official: str, interpretation_status: str) -> str:
    """What-if treatment honoring the survey's written evidence.

    Only a score_comment_conflict flips the treatment: the binary
    interpretation is backwards relative to the survey's own words
    (FAIL with positive resolved text -> PASS; PASS with negative
    unresolved text -> FAIL). Every other status — consistent,
    inconclusive, insufficient evidence, not_screened — keeps the
    official treatment: no evidence, no adjustment.

    Deterministic and fully explicit. The official treatment is never
    altered; this feeds a separate, clearly-labeled adjusted view.
    """
    if interpretation_status == "score_comment_conflict":
        return "FAIL" if official == "PASS" else "PASS"
    return official


def running_adjusted_scorecard(results: list) -> dict[str, ScorecardPoint]:
    """Per-survey adjusted scorecard, chronological per branch.

    Takes InterpretationResults (which carry official_treatment and
    interpretation_status) and returns {survey_id: ScorecardPoint} computed
    with adjusted_treatment instead of the official pass/fail. Old-way rows
    (not_screened) adjust to their official treatment — no evidence was
    examined, so nothing changes.
    """
    by_branch: dict[str, list] = {}
    for r in results:
        by_branch.setdefault(r.branch, []).append(r)

    points: dict[str, ScorecardPoint] = {}
    for branch, branch_results in by_branch.items():
        ordered = sorted(branch_results,
                         key=lambda r: (r.timestamp, r.survey_id))
        passing, total = 0, 0
        for r in ordered:
            before = scorecard_pct(passing, total)
            if adjusted_treatment(r.official_treatment,
                                  r.interpretation_status) == "PASS":
                passing += 1
            total += 1
            after = scorecard_pct(passing, total)
            assert after is not None
            delta = after - before if before is not None else None
            t_before, t_after = tier_for(before), tier_for(after)
            assert t_after is not None
            crossed = t_before is not None and t_before != t_after
            points[r.survey_id] = ScorecardPoint(
                before_pct=round(before, 2) if before is not None else None,
                after_pct=round(after, 2),
                delta_pp=round(delta, 2) if delta is not None else None,
                tier_before=t_before,
                tier_after=t_after,
                tier_crossed=crossed,
            )
    return points


def scorecard_pct(passing: int, total: int) -> float | None:
    if total == 0:
        return None
    return 100.0 * passing / total


def running_scorecard(surveys: list[Survey]) -> dict[str, ScorecardPoint]:
    """Per-survey scorecard impact, processed in strict chronological order.

    Returns {survey_id: ScorecardPoint}. Input row order never matters:
    surveys are sorted by (timestamp, survey_id) before processing, so the
    running scorecard is deterministic.
    """
    by_branch: dict[str, list[Survey]] = {}
    for s in surveys:
        by_branch.setdefault(s.branch, []).append(s)

    points: dict[str, ScorecardPoint] = {}
    for branch, branch_surveys in by_branch.items():
        ordered = sorted(branch_surveys, key=lambda s: (s.timestamp, s.survey_id))
        passing, total = 0, 0
        for s in ordered:
            before = scorecard_pct(passing, total)
            if is_pass(s.score):
                passing += 1
            total += 1
            after = scorecard_pct(passing, total)
            assert after is not None
            delta = after - before if before is not None else None
            t_before, t_after = tier_for(before), tier_for(after)
            assert t_after is not None
            # A branch's first survey initializes the scorecard; that is not
            # a crossing. Only a real tier change on an established
            # scorecard counts.
            crossed = t_before is not None and t_before != t_after
            points[s.survey_id] = ScorecardPoint(
                before_pct=round(before, 2) if before is not None else None,
                after_pct=round(after, 2),
                delta_pp=round(delta, 2) if delta is not None else None,
                tier_before=t_before,
                tier_after=t_after,
                tier_crossed=crossed,
            )
    return points
