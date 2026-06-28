"""Signal B — stylometric heuristics (pure Python, no external libraries).

Measures *structural* properties of text that differ between human and AI writing:
burstiness (sentence-length variance), lexical diversity (type-token ratio),
punctuation density, and mean sentence length. AI text trends toward low burstiness
and middling, consistent diversity; human writing is more variable.

This signal has no understanding of meaning — it only sees shape. Its blind spots are
documented in planning.md (formal human prose and short repetitive text both read as
"AI-like").
"""
from __future__ import annotations

import re
from statistics import pvariance
from typing import Dict

_SENTENCE_SPLIT = re.compile(r"[.!?]+(?:\s|$)")
_WORD = re.compile(r"[A-Za-z']+")
_PUNCT = re.compile(r"[,;:\-—()\"'.!?]")


def _split_sentences(text: str) -> list[str]:
    parts = [s.strip() for s in _SENTENCE_SPLIT.split(text) if s.strip()]
    return parts or ([text.strip()] if text.strip() else [])


def compute_metrics(text: str) -> Dict[str, float]:
    """Return the raw stylometric metrics for a piece of text."""
    words = _WORD.findall(text.lower())
    sentences = _split_sentences(text)
    word_count = len(words)

    sentence_lengths = [len(_WORD.findall(s)) for s in sentences]
    sentence_lengths = [n for n in sentence_lengths if n > 0]

    mean_sentence_len = (
        sum(sentence_lengths) / len(sentence_lengths) if sentence_lengths else 0.0
    )
    # Burstiness: variance of sentence length. Higher = more human-like.
    sentence_len_variance = (
        pvariance(sentence_lengths) if len(sentence_lengths) > 1 else 0.0
    )
    # Type-token ratio: unique words / total words. Vocabulary diversity.
    type_token_ratio = (len(set(words)) / word_count) if word_count else 0.0
    # Punctuation density: punctuation marks per word.
    punct_density = (len(_PUNCT.findall(text)) / word_count) if word_count else 0.0

    return {
        "word_count": float(word_count),
        "mean_sentence_length": round(mean_sentence_len, 3),
        "sentence_length_variance": round(sentence_len_variance, 3),
        "type_token_ratio": round(type_token_ratio, 3),
        "punctuation_density": round(punct_density, 3),
    }


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def stylometry_signal(text: str) -> Dict[str, object]:
    """Map raw metrics to an AI-probability in [0, 1].

    The heuristic awards "AI-likelihood" points for the structural traits AI text
    tends to show, then averages them. Each sub-score is itself in [0, 1].
    """
    m = compute_metrics(text)

    # Very short inputs carry little structural signal — abstain toward 0.5.
    if m["word_count"] < 25:
        return {
            "ai_probability": 0.5,
            "metrics": m,
            "note": "input too short for reliable stylometry; abstaining toward 0.5",
        }

    # Burstiness via coefficient of variation (std / mean sentence length). This is
    # length-normalized, so it compares across short and long texts. Humans vary their
    # sentence length a lot (high CV ~0.5–0.9); AI is more uniform (low CV ~0.2–0.4).
    # Low CV => AI-like. This is the most discriminative structural trait.
    mean_len = m["mean_sentence_length"]
    std_len = m["sentence_length_variance"] ** 0.5
    cv = (std_len / mean_len) if mean_len else 0.0
    burstiness_ai = _clamp(1.0 - (cv - 0.2) / 0.6)

    # Type-token ratio: very repetitive text (low TTR) reads AI-/template-like. Maps a
    # low diversity to AI; high diversity to human. (Weak on short text — low weight.)
    ttr = m["type_token_ratio"]
    diversity_ai = _clamp(1.0 - (ttr - 0.4) / 0.5)

    # Punctuation density: AI tends to moderate, consistent punctuation (~0.12–0.20).
    pd = m["punctuation_density"]
    punct_ai = _clamp(1.0 - abs(pd - 0.16) * 4.0)

    # Mean sentence length: AI favors medium-long, even sentences (~15–25 words).
    msl = m["mean_sentence_length"]
    length_ai = _clamp(1.0 - abs(msl - 20.0) / 20.0)

    # Burstiness is the most discriminative trait, so weight it most.
    ai_probability = (
        0.55 * burstiness_ai
        + 0.15 * diversity_ai
        + 0.10 * punct_ai
        + 0.20 * length_ai
    )

    return {
        "ai_probability": round(_clamp(ai_probability), 4),
        "metrics": m,
        "sub_scores": {
            "coefficient_of_variation": round(cv, 3),
            "burstiness_ai": round(burstiness_ai, 3),
            "diversity_ai": round(diversity_ai, 3),
            "punct_ai": round(punct_ai, 3),
            "length_ai": round(length_ai, 3),
        },
    }
