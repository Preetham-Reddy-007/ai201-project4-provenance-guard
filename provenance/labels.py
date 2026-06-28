"""Transparency label generation.

Maps the scored result to plain-language label text a non-technical reader can
understand. Three variants — high-confidence AI, high-confidence human, uncertain —
written out verbatim in planning.md and the README.
"""
from __future__ import annotations

from typing import Dict


def build_label(attribution: str, ai_probability: float, display_confidence) -> Dict[str, str]:
    """Return {variant, text} for the given scored result."""
    score = round(ai_probability, 2)

    if attribution == "likely_ai":
        pct = round((display_confidence if display_confidence is not None else ai_probability) * 100)
        text = (
            f"\U0001F916 Likely AI-generated — Our analysis suggests this text was "
            f"probably produced by an AI system (about {pct}% confidence). This is an "
            f"automated estimate, not a certainty. If you wrote this yourself, you can "
            f"appeal this label."
        )
        variant = "high_confidence_ai"

    elif attribution == "likely_human":
        pct = round((display_confidence if display_confidence is not None else (1 - ai_probability)) * 100)
        text = (
            f"✍️ Likely human-written — Our analysis found no strong signs of "
            f"AI generation (about {pct}% confidence this is human-written). This is an "
            f"automated estimate, not a guarantee of authorship."
        )
        variant = "high_confidence_human"

    else:  # uncertain
        text = (
            f"❓ Uncertain origin — Our signals disagree about whether this text is "
            f"human-written or AI-generated, so we're not labeling it either way "
            f"(AI-likelihood ≈ {score}). Treat the origin as unverified."
        )
        variant = "uncertain"

    return {"variant": variant, "text": text}
