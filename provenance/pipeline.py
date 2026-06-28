"""Detection pipeline orchestration: run both signals, score, build the label.

Kept separate from the Flask layer so it can be tested directly (see
scripts/calibrate.py) without an HTTP server.
"""
from __future__ import annotations

from typing import Dict

from .labels import build_label
from .llm_signal import llm_signal
from .scoring import combine_signals
from .stylometry import stylometry_signal


def analyze(text: str) -> Dict[str, object]:
    """Run the full detection pipeline on a piece of text."""
    sig_a = llm_signal(text)
    sig_b = stylometry_signal(text)

    p_llm = sig_a["ai_probability"] if sig_a["available"] else None
    p_sty = float(sig_b["ai_probability"])

    scored = combine_signals(p_llm, p_sty)
    label = build_label(
        scored["attribution"], scored["ai_probability"], scored["display_confidence"]
    )

    return {
        "ai_probability": scored["ai_probability"],
        "attribution": scored["attribution"],
        "display_confidence": scored["display_confidence"],
        "scoring_mode": scored["scoring_mode"],
        "label": label,
        "signals": {
            "llm": sig_a,
            "stylometry": sig_b,
        },
    }
