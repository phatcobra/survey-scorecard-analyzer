"""Summary report for survey/scorecard interpretation."""

from __future__ import annotations

from collections import Counter

from .schemas import InterpretationResult
from .scorecard import bonus_for


def summarize(results: list[InterpretationResult]) -> dict:
    branches: dict[str, list[InterpretationResult]] = {}
    for r in results:
        branches.setdefault(r.branch, []).append(r)

    branch_summary = {}
    for branch, rs in sorted(branches.items()):
        ordered = sorted(rs, key=lambda r: (r.timestamp, r.survey_id))
        last = ordered[-1]
        branch_summary[branch] = {
            "surveys": len(rs),
            "final_scorecard_pct": last.scorecard_after_pct,
            "tier": last.tier_after,
            "bonus_per_person": bonus_for(last.tier_after),
        }

    return {
        "n_surveys": len(results),
        "branch_summary": branch_summary,
        "treatment_counts": dict(Counter(r.official_treatment for r in results)),
        "interpretation_counts": dict(Counter(r.interpretation_status for r in results)),
        "resolution_counts": dict(Counter(r.resolution for r in results)),
        "tier_crossings": [r for r in results if r.tier_crossed],
        "conflicts": [r for r in results if r.conflict_flag],
        "needs_human_review": [r for r in results if r.needs_human_review],
    }


def render_text(summary: dict) -> str:
    lines = [
        "SURVEY / SCORECARD INTERPRETATION REPORT (synthetic data)",
        "=" * 60,
        f"Surveys analyzed: {summary['n_surveys']}",
        "",
        "Branch scorecards (top-2-box % of 9-10 scores):",
    ]
    for branch, b in summary["branch_summary"].items():
        lines.append(
            f"  {branch}: {b['surveys']} surveys -> "
            f"{b['final_scorecard_pct']}% ({b['tier']}, "
            f"${b['bonus_per_person']}/person)"
        )
    lines += ["", "Official scorecard treatment (score-only, comment-independent):"]
    for s, c in sorted(summary["treatment_counts"].items()):
        lines.append(f"  {s}: {c}")
    lines += ["", "Interpretation status:"]
    for s, c in sorted(summary["interpretation_counts"].items()):
        lines.append(f"  {s}: {c}")
    lines += ["", "Resolution signal:"]
    for s, c in sorted(summary["resolution_counts"].items()):
        lines.append(f"  {s}: {c}")
    lines += ["", f"Tier-crossing surveys: {len(summary['tier_crossings'])}"]
    for r in summary["tier_crossings"]:
        lines.append(
            f"  [{r.survey_id}] {r.branch}: {r.scorecard_before_pct}% "
            f"({r.tier_before}) -> {r.scorecard_after_pct}% ({r.tier_after}), "
            f"score={r.score} ({r.official_treatment})"
        )
    lines += ["", f"Score/comment conflicts: {len(summary['conflicts'])}"]
    for r in summary["conflicts"]:
        lines.append(
            f"  [{r.survey_id}] teller={r.teller} score={r.score} "
            f"({r.official_treatment}) sentiment={r.sentiment_label} "
            f"resolution={r.resolution}"
        )
        lines.append(f"    comment: {r.comment[:90]}")
        lines.append(f"    why: {r.reason}")
    return "\n".join(lines)
