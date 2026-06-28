"""Confidence scoring — combine the two signals into one calibrated AI-probability.

The combined score ``p`` in [0, 1] is the system's estimate that the text is
AI-generated. ``p ≈ 0.5`` means genuine uncertainty, not "half AI". Thresholds and the
false-positive asymmetry are documented in planning.md.
"""
from __future__ import annotations

from typing import Dict, Optional

# Threshold boundaries between the three label variants.
AI_THRESHOLD = 0.70       # p >= this  -> likely_ai (deliberately high; FP-averse)
HUMAN_THRESHOLD = 0.30    # p <= this  -> likely_human

# Signal weights when both are available.
LLM_WEIGHT = 0.60
STYLOMETRY_WEIGHT = 0.40


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def attribution_for(p: float) -> str:
    if p >= AI_THRESHOLD:
        return "likely_ai"
    if p <= HUMAN_THRESHOLD:
        return "likely_human"
    return "uncertain"


def combine_signals(p_llm: Optional[float], p_sty: float) -> Dict[str, object]:
    """Combine signal outputs into a single confidence-scored result.

    Args:
        p_llm: LLM AI-probability, or None if the LLM signal was unavailable.
        p_sty: stylometry AI-probability (always present).
    """
    if p_llm is not None:
        combined = LLM_WEIGHT * p_llm + STYLOMETRY_WEIGHT * p_sty
        mode = "two_signal"
    else:
        # Only one weak structural signal: shrink toward 0.5 so we can never assert a
        # high-confidence verdict off stylometry alone.
        combined = 0.5 + 0.6 * (p_sty - 0.5)
        mode = "stylometry_only_fallback"

    combined = round(_clamp(combined), 4)
    attribution = attribution_for(combined)

    # Displayed confidence: confidence in the verdict we actually give.
    if attribution == "likely_ai":
        display_confidence = combined
    elif attribution == "likely_human":
        display_confidence = 1.0 - combined
    else:
        display_confidence = None  # uncertain -> we report a range, not a number

    return {
        "ai_probability": combined,
        "attribution": attribution,
        "display_confidence": (
            round(display_confidence, 4) if display_confidence is not None else None
        ),
        "scoring_mode": mode,
    }
