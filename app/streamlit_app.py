"""Streamlit dashboard: survey/scorecard interpretation analyzer.

Run from the project root (venv):
    streamlit run app/streamlit_app.py

Reads data/analyzed_surveys.csv produced by `python3 src/main.py`.
Advisory only: surfaces interpretation conflicts and scorecard impact
for human review. Never changes a score or decides employment outcomes.

The dataset holds two cohorts of 50 branches each:
  new_way ... full analyzer (scorecard + interpretation screening)
  old_way ... scorecard only; the interpretation layer is never applied,
              so score/comment conflicts in these branches go unflagged
              by construction. Same underlying survey distributions —
              the cohorts differ only in the method applied.
"""

from __future__ import annotations

import csv
import os
from collections import Counter

import altair as alt
import pandas as pd
import streamlit as st

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_PATH = os.path.join(BASE, "data", "analyzed_surveys.csv")

COHORT_LABELS = {
    "compare": "Old way vs new way (comparison)",
    "new_way": "New way — analyzer (50 branches)",
    "old_way": "Old way — scorecard only (50 branches)",
}


def load_rows():
    with open(CSV_PATH, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def pct(x):
    try:
        return float(x) if x not in (None, "") else None
    except (TypeError, ValueError):
        return None


def cohort_stats(rows, cohort):
    rs = [r for r in rows if r.get("cohort", "new_way") == cohort]
    branches = sorted({r["branch"] for r in rs})
    conflicts = [r for r in rs if r["interpretation_status"] == "score_comment_conflict"]
    crossings = [r for r in rs if r["tier_crossed"] == "True"]
    explained = [r for r in crossings if r["conflict_flag"] == "True"]
    return {
        "surveys": len(rs), "branches": len(branches),
        "conflicts": len(conflicts), "crossings": len(crossings),
        "explained": len(explained),
    }


st.set_page_config(page_title="Survey / Scorecard Interpretation", layout="wide")
st.title("Customer Survey Interpretation & Scorecard Impact Analyzer")
st.caption("Synthetic data. Advisory only — exposes measurement conflicts for "
           "human review; does not change scores or decide employment outcomes.")

rows = load_rows()

mode = st.selectbox("Method", list(COHORT_LABELS), format_func=COHORT_LABELS.get)

if mode == "compare":
    old = cohort_stats(rows, "old_way")
    new = cohort_stats(rows, "new_way")
    new_rows = [r for r in rows if r.get("cohort", "new_way") == "new_way"]
    reclassified = sum(1 for r in new_rows
                       if r["interpretation_status"] == "score_comment_conflict")
    avoided = sum(1 for r in new_rows
                  if r["tier_crossed"] == "True"
                  and r["adjusted_tier_crossed"] != "True")
    st.subheader("What the new way catches that the old way buries")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Old way — scorecard only** (50 branches)")
        st.metric("Surveys (never screened)", old["surveys"])
        st.metric("Tier crossings", old["crossings"])
        st.metric("Conflicts surfaced", 0)
        st.metric("Tier crossings with a flagged cause", 0)
    with c2:
        st.markdown("**New way — analyzer** (50 branches)")
        st.metric("Surveys screened", new["surveys"])
        st.metric("Tier crossings", new["crossings"])
        st.metric("Conflicts surfaced for human review", new["conflicts"])
        st.metric("Tier crossings with a flagged cause", new["explained"])
    st.markdown("**Adjusted (\"truer\") scorecard** — what the branch scorecards "
                "would look like if written evidence were honored:")
    a1, a2 = st.columns(2)
    a1.metric("Surveys reclassified by written evidence", reclassified)
    a2.metric("Official tier crossings the adjusted view avoids", avoided)
    st.caption(
        "Controlled comparison: both cohorts were generated from the same survey "
        "distributions, so the underlying conflicts exist in both. The old-way "
        "branches were never screened for them (interpretation_status = "
        "'not_screened'); the new-way branches surface each one with its written "
        "evidence and scorecard impact. The adjusted scorecard is a what-if view: "
        "a conflicting survey counts the way its written evidence reads "
        "(an 8/10 with a great comment counts as a pass). The official scorecard "
        "is never altered.")
    st.divider()

# ---- per-cohort (or comparison-wide) branch explorer ----
if mode == "compare":
    brows_all = sorted(rows, key=lambda r: (r.get("cohort", ""), r["branch"],
                                            r["timestamp"], r["survey_id"]))
    branch_options = ["All branches"] + sorted({r["branch"] for r in rows})
else:
    brows_all = sorted([r for r in rows if r.get("cohort", "new_way") == mode],
                       key=lambda r: (r["branch"], r["timestamp"], r["survey_id"]))
    branch_options = ["All branches"] + sorted({r["branch"] for r in brows_all})

branch = st.selectbox("Branch", branch_options)
if branch == "All branches":
    brows = brows_all
    all_view = True
else:
    brows = sorted([r for r in brows_all if r["branch"] == branch],
                   key=lambda r: (r["timestamp"], r["survey_id"]))
    all_view = False

is_old_view = mode == "old_way" or (
    mode == "compare" and brows and all(r.get("cohort") == "old_way" for r in brows))

conflicts = [r for r in brows if r["interpretation_status"] == "score_comment_conflict"]
crossings = [r for r in brows if r["tier_crossed"] == "True"]

c1, c2, c3, c4 = st.columns(4)
c1.metric("Surveys", len(brows))
c2.metric("Score/comment conflicts", len(conflicts))
c3.metric("Tier-crossing surveys", len(crossings))
if all_view:
    c4.metric("Branches", len({r["branch"] for r in brows}))
else:
    last = brows[-1]
    bonus = {'gold': 300, 'silver': 150}.get(last['tier_after'], 0)
    agree = (last["scorecard_after_pct"] == last["adjusted_after_pct"]
             and last["tier_after"] == last["adjusted_tier_after"])
    if is_old_view or agree:
        c4.metric("Scorecard (final)", f"{last['scorecard_after_pct']}%",
                  f"{last['tier_after']} (${bonus}/person)")
    else:
        c4.metric("Official → Adjusted",
                  f"{last['scorecard_after_pct']}% → {last['adjusted_after_pct']}%",
                  f"{last['tier_after']} → {last['adjusted_tier_after']}")

def key_moments(brows):
    """Plain-English descriptions of surveys where the adjusted scorecard
    disagrees with the official one."""
    msgs = []
    for i, r in enumerate(brows, start=1):
        if r["interpretation_status"] != "score_comment_conflict":
            continue
        off_cross = r["tier_crossed"] == "True"
        adj_cross = r["adjusted_tier_crossed"] == "True"
        if not (off_cross or adj_cross):
            continue
        positive = r["official_treatment"] == "FAIL"
        reads = "glowing" if positive else "hostile"
        counts_as = "a pass" if positive else "a fail"
        if off_cross and not adj_cross:
            msgs.append(
                f"Survey {i} ({r['survey_id']}): scored {r['score']}/10 with a "
                f"{reads} comment. The official scorecard moved the branch "
                f"{r['tier_before']} → {r['tier_after']} "
                f"({r['scorecard_before_pct']}% → {r['scorecard_after_pct']}%). "
                f"The adjusted scorecard counts it as {counts_as} — "
                f"{r['adjusted_tier_before']} → {r['adjusted_tier_after']} "
                f"({r['adjusted_before_pct']}% → {r['adjusted_after_pct']}%), "
                f"no tier crossing.")
        elif adj_cross and not off_cross:
            msgs.append(
                f"Survey {i} ({r['survey_id']}): scored {r['score']}/10 with a "
                f"{reads} comment. The official scorecard shows no tier "
                f"crossing ({r['tier_before']} → {r['tier_after']}), but the "
                f"adjusted scorecard — counting it as {counts_as} — moves the "
                f"branch {r['adjusted_tier_before']} → {r['adjusted_tier_after']} "
                f"({r['adjusted_before_pct']}% → {r['adjusted_after_pct']}%).")
    return msgs


if not all_view and not is_old_view:
    moments = key_moments(brows)
    if moments:
        st.subheader("Key moments — where the two scorecards disagree")
        for m in moments[:3]:
            st.info(m)
        if len(moments) > 3:
            st.caption(f"+ {len(moments) - 3} more — see the survey list below.")

st.subheader("Branch scorecard over time (top-2-box % of 9–10)")
if all_view:
    # Cohort-average lines. One line per branch (100 lines) is unreadable
    # spaghetti; the average per survey-step shows the comparison cleanly.
    # New-way also gets its adjusted ("truer") average.
    # IMPORTANT: only steps where EVERY branch in the cohort contributes
    # (min branch length). Beyond that only the downtown/uptown fixture
    # branches have surveys, and the average would spike on composition
    # change alone — a survivorship artifact, not a real effect.
    series = []
    def avg_line(crows, label, col):
        ordered = {}
        for b in {r["branch"] for r in crows}:
            ordered[b] = sorted([r for r in crows if r["branch"] == b],
                                key=lambda r: (r["timestamp"], r["survey_id"]))
        max_step = min(len(v) for v in ordered.values())
        by_step = {}
        for b, br in ordered.items():
            for i, r in enumerate(br, start=1):
                if i > max_step:
                    break
                v = pct(r[col])
                if v is not None:
                    by_step.setdefault(i, []).append(v)
        for i in sorted(by_step):
            vals = by_step[i]
            series.append({"step": i, "scorecard": sum(vals) / len(vals),
                           "method": label})
    for cohort, label in (("old_way", "Old way"),
                          ("new_way", "New way — official")):
        crows = [r for r in brows if r.get("cohort", "new_way") == cohort]
        if crows:
            avg_line(crows, label, "scorecard_after_pct")
    new_rows = [r for r in brows if r.get("cohort", "new_way") == "new_way"]
    if new_rows and not is_old_view:
        avg_line(new_rows, "New way — adjusted", "adjusted_after_pct")
    adf = pd.DataFrame(series)
    abase = (alt.Chart(adf)
             .mark_line()
             .encode(x=alt.X("step:Q", title="Survey number (step)"),
                     y=alt.Y("scorecard:Q", title="Avg scorecard %"),
                     color=alt.Color("method:N", title=""),
                     strokeDash=alt.condition(
                         alt.datum.method == "Old way",
                         alt.value([6, 4]), alt.value([1, 0])),
                     tooltip=["method", "step",
                              alt.Tooltip("scorecard:Q", format=".1f")]))
    st.altair_chart(abase.properties(height=300), use_container_width=True)
    st.caption("Average running scorecard per survey-step, steps 1–24: every "
               "branch has at least 24 surveys, so each point averages the "
               "full cohort. (Past step 24 only the downtown/uptown fixture "
               "branches have surveys — including them spikes the average on "
               "composition change alone, so they're excluded.) The dashed "
               "old-way line tracks the new-way official line almost exactly: "
               "the underlying scores are the same. The difference between "
               "the methods isn't the scores — it's what gets surfaced.")
else:
    # Step-numbered x-axis (readable), gold/silver threshold lines, and red
    # diamonds marking official tier crossings.
    df_rows = []
    for i, r in enumerate(brows, start=1):
        df_rows.append({"step": i, "scorecard": pct(r["scorecard_after_pct"]),
                        "view": "Official", "survey": r["survey_id"],
                        "score": r["score"]})
        if not is_old_view:
            df_rows.append({"step": i,
                            "scorecard": pct(r["adjusted_after_pct"]),
                            "view": "Adjusted (truer)", "survey": r["survey_id"],
                            "score": r["score"]})
    df = pd.DataFrame(df_rows)
    lines = (alt.Chart(df)
             .mark_line()
             .encode(x=alt.X("step:Q", title="Survey number"),
                     y=alt.Y("scorecard:Q", title="Scorecard %",
                             scale=alt.Scale(domain=[0, 100])),
                     color=alt.Color("view:N", title=""),
                     tooltip=["survey", "score", "scorecard"]))
    gold = (alt.Chart(pd.DataFrame({"y": [95]}))
            .mark_rule(strokeDash=[6, 4], color="darkgoldenrod")
            .encode(y="y:Q"))
    silver = (alt.Chart(pd.DataFrame({"y": [90]}))
              .mark_rule(strokeDash=[6, 4], color="gray")
              .encode(y="y:Q"))
    layers = [lines, gold, silver]
    cross = [{"step": i, "scorecard": pct(r["scorecard_after_pct"])}
             for i, r in enumerate(brows, start=1)
             if r["tier_crossed"] == "True"]
    if cross:
        layers.append(
            alt.Chart(pd.DataFrame(cross))
            .mark_point(size=90, shape="diamond", color="firebrick")
            .encode(x="step:Q", y="scorecard:Q",
                    tooltip=[alt.Tooltip("step:Q", title="Survey number")]))
    st.altair_chart(alt.layer(*layers).properties(height=320),
                    use_container_width=True)
    st.caption("Dashed lines: gold threshold (95%) and silver threshold (90%). "
               "Red diamonds: official tier crossings. Hover any point for the "
               "survey ID and score.")
st.caption("Tier bands: gold ≥ 95% ($300/person), silver 90–95% ($150/person), "
           "below 90% no bonus. A single 1–8 survey can move the branch across a band.")

st.subheader("Surveys needing human review (score/comment conflicts)")
if is_old_view:
    st.write("The old way never screens written feedback — none of these "
             f"{len(brows)} surveys were ever checked for score/comment conflicts. "
             "Any conflicts in this data went unflagged by construction.")
else:
    flagged = [r for r in brows if r["needs_human_review"] == "True"]
    if not flagged:
        st.write("None.")
    for r in flagged:
        title = (f"{r['survey_id']}: score {r['score']}/10 ({r['official_treatment']}) — "
                 f"{r['interpretation_status']}"
                 + (" — TIER CROSSING" if r["tier_crossed"] == "True" else ""))
        with st.expander(title):
            st.write(f"**Comment:** {r['comment'] or '(blank)'}")
            st.write(f"**Teller:** {r['teller']} · **When:** {r['timestamp']}")
            st.write(f"**Text evidence:** sentiment={r['sentiment_label'] or 'n/a'} "
                     f"({r['sentiment_status']}), resolution={r['resolution']}, "
                     f"positive themes=[{r['positive_themes'] or '—'}], "
                     f"negative themes=[{r['negative_themes'] or '—'}]")
            before = r["scorecard_before_pct"] or "—"
            st.write(f"**Scorecard impact:** {before}% ({r['tier_before'] or '—'}) → "
                     f"{r['scorecard_after_pct']}% ({r['tier_after']})"
                     + (f" — Δ {r['scorecard_delta_pp']}pp" if r["scorecard_delta_pp"] else ""))
            st.write(f"**Finding:** {r['reason']}")

st.subheader("Tier crossings (scorecard-impact events, not interpretation problems)")
if not crossings:
    st.write("None.")
for r in crossings:
    st.write(f"- **{r['survey_id']}** ({r['branch']}): score {r['score']}/10 ({r['official_treatment']}) moved "
             f"the branch from {r['scorecard_before_pct']}% ({r['tier_before']}) to "
             f"{r['scorecard_after_pct']}% ({r['tier_after']})"
             + (" — also a score/comment conflict" if r["conflict_flag"] == "True" else ""))

st.subheader("All surveys")
st.dataframe(
    [{"survey": r["survey_id"], "branch": r["branch"], "score": r["score"],
      "treatment": r["official_treatment"],
      "interpretation": r["interpretation_status"],
      "conflict": r["conflict_flag"],
      "tier crossed": r["tier_crossed"],
      "review": r["needs_human_review"],
      "sentiment": r["sentiment_label"] or "n/a",
      "resolution": r["resolution"],
      "Δpp": r["scorecard_delta_pp"] or "—"}
     for r in brows],
    use_container_width=True,
)

with st.expander("Methodology & boundaries"):
    st.write(
        "- **Official treatment** is a pure function of the score (≥9 PASS, ≤8 FAIL); "
        "the comment can never change it.\n"
        "- **Conflict** = the binary treatment contradicts the written evidence "
        "(either direction: FAIL with positive resolved text, or PASS with "
        "negative unresolved text).\n"
        "- **Scorecard** = % of 9–10 surveys, computed chronologically per branch; "
        "each survey shows before/after/Δ and any bonus-tier crossing.\n"
        "- **Adjusted (\"truer\") scorecard** = a what-if view honoring written "
        "evidence. Rule (deterministic, explicit): a `score_comment_conflict` "
        "survey counts the way its comment reads — an 8/10 with a great comment "
        "counts as a pass, a 10/10 with a hostile unresolved comment counts as "
        "a fail. Every other status keeps the official treatment: no evidence, "
        "no adjustment. The official scorecard is never altered; the adjusted "
        "columns sit alongside it.\n"
        "- **Old way vs new way** is a controlled comparison: both cohorts were "
        "generated from the same survey distributions. Old-way branches got the "
        "scorecard only (interpretation_status = 'not_screened'); new-way branches "
        "got the full analyzer.\n"
        "- Blank comments are *no* evidence, not negative evidence.\n"
        "- This tool surfaces conflicts for human review. It does not alter "
        "ratings and does not decide bonuses, promotions, discipline, raises, "
        "or performance ratings.")
