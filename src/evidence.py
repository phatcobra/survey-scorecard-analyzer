"""Written-feedback evidence extraction (dimension 2).

The scorecard throws the comment away; this module reads it. Sentiment
comes from the shared rule-based SentimentProvider (zero cost,
deterministic). Service themes and the resolution signal are keyword
rules over the comment text.

A blank comment is not negative evidence — it is *no* evidence, and the
interpreter treats it as insufficient_text_evidence rather than guessing.
"""

from __future__ import annotations

from .schemas import TextEvidence
from .sentiment import SentimentEvidence

THEME_KEYWORDS = {
    "professionalism": {"professional", "courteous", "polite", "friendly", "rude"},
    "knowledge": {"knowledgeable", "answered", "clear", "confusing"},
    "responsiveness": {"quick", "fast", "efficient", "wait", "waiting", "slow"},
    "resolution": {"resolved", "unresolved", "fixed", "solved", "broken"},
    "care": {"took care of", "taken care of", "needs", "helped", "helpful"},
}

# Resolution is checked against unresolved FIRST: "never resolved" must not
# match the resolved list via the substring "resolved".
UNRESOLVED_PHRASES = frozenset({
    "not resolved", "unresolved", "never resolved", "wasn't resolved",
    "was not resolved", "still waiting", "didn't help", "did not help",
    "never helped", "no help", "couldn't help", "could not help",
    "didn't take care", "did not take care",
})
RESOLVED_PHRASES = frozenset({
    "took care of", "taken care of", "all my needs", "got what i needed",
    "resolved", "fixed it", "solved", "handled everything", "took care",
})


def _resolution_signal(text: str) -> str:
    lowered = text.lower()
    if any(p in lowered for p in UNRESOLVED_PHRASES):
        return "unresolved"
    if any(p in lowered for p in RESOLVED_PHRASES):
        return "resolved"
    return "unknown"


_SENTIMENT_POLARITY = {
    "strongly_positive": 2, "positive": 1, "neutral": 0, "mixed": 0, "negative": -2,
}


def _themes(text: str, label: str | None) -> tuple[tuple, tuple]:
    # Themes are directional: polarity comes from the sentiment label, so a
    # "wait time" mention in praise is a positive theme and in a complaint a
    # negative one. This is what lets the interpreter say "no stated service
    # failure" (empty negative_themes) for a positive comment.
    polarity = _SENTIMENT_POLARITY.get(label.lower(), 0) if label else 0
    lowered = text.lower()
    pos_themes, neg_themes = [], []
    for theme, keywords in THEME_KEYWORDS.items():
        if any(k in lowered for k in keywords):
            if polarity >= 0:
                pos_themes.append(theme)
            if polarity <= 0:
                neg_themes.append(theme)
    return tuple(sorted(set(pos_themes))), tuple(sorted(set(neg_themes)))


def extract_evidence(comment: str, ev: SentimentEvidence) -> TextEvidence:
    has_text = bool(comment and comment.strip())
    if not has_text:
        return TextEvidence(has_text=False, sentiment_status="unavailable",
                            sentiment_label=None, resolution="unknown")
    if ev.status != "available":
        return TextEvidence(has_text=True, sentiment_status="unavailable",
                            sentiment_label=None, resolution=_resolution_signal(comment))
    pos_themes, neg_themes = _themes(comment, ev.label)
    return TextEvidence(
        has_text=True,
        sentiment_status="available",
        sentiment_label=ev.label,
        positive_themes=pos_themes,
        negative_themes=neg_themes,
        resolution=_resolution_signal(comment),
    )
