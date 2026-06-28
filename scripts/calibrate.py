"""Calibration harness — run the pipeline on labeled sample inputs and print scores.

Used to verify (Milestone 4) that the combined confidence score varies meaningfully
across clearly-AI, clearly-human, and borderline inputs, and that each input lands in a
sensible label variant. Run from the repo root:

    python scripts/calibrate.py

Works with or without GROQ_API_KEY. Without a key it exercises the stylometry-only
fallback path.
"""
from __future__ import annotations

import os
import sys

# Windows consoles default to cp1252 and choke on the label emoji — force UTF-8.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except AttributeError:  # pragma: no cover
    pass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv  # noqa: E402

from provenance.pipeline import analyze  # noqa: E402

load_dotenv()

SAMPLES = {
    "clearly AI-generated": (
        "Artificial intelligence represents a transformative paradigm shift in modern "
        "society. It is important to note that while the benefits of AI are numerous, "
        "it is equally essential to consider the ethical implications. Furthermore, "
        "stakeholders across various sectors must collaborate to ensure responsible "
        "deployment."
    ),
    "clearly human-written": (
        "ok so i finally tried that new ramen place downtown and honestly? "
        "underwhelming. the broth was fine but they put WAY too much sodium in it and "
        "i was thirsty for like three hours after. my friend got the spicy version and "
        "said it was better. probably won't go back unless someone drags me there"
    ),
    "borderline: formal human": (
        "The relationship between monetary policy and asset price inflation has been "
        "extensively studied in the literature. Central banks face a fundamental "
        "tension between their mandate for price stability and the unintended "
        "consequences of prolonged low interest rates on equity and real estate "
        "valuations."
    ),
    "borderline: lightly edited AI": (
        "I've been thinking a lot about remote work lately. There are genuine "
        "tradeoffs — flexibility and no commute on one side, isolation and blurred "
        "work-life boundaries on the other. Studies show productivity varies widely by "
        "individual and role type."
    ),
}


def main() -> None:
    have_key = bool(os.environ.get("GROQ_API_KEY"))
    print(f"GROQ_API_KEY present: {have_key}\n" + "=" * 70)
    for name, text in SAMPLES.items():
        r = analyze(text)
        sty = r["signals"]["stylometry"]["ai_probability"]
        llm = r["signals"]["llm"]["ai_probability"]
        metrics = r["signals"]["stylometry"].get("metrics", {})
        subs = r["signals"]["stylometry"].get("sub_scores", {})
        print(f"\n[{name}]")
        print(f"  metrics: {metrics}")
        print(f"  sub_scores: {subs}")
        print(f"  stylometry p={sty}   llm p={llm}   mode={r['scoring_mode']}")
        print(f"  combined p={r['ai_probability']}  ->  {r['attribution']} "
              f"({r['label']['variant']})")
        print(f"  label: {r['label']['text']}")


if __name__ == "__main__":
    main()
