"""Provenance Guard — Flask application.

Endpoints:
    POST /submit   — classify a piece of text; returns content_id, attribution,
                     confidence, transparency label, and per-signal scores.
    POST /appeal   — contest a classification; flips status to under_review and logs it.
    GET  /log      — recent structured audit-log entries.
    GET  /health   — liveness check.
"""
from __future__ import annotations

import uuid

from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from provenance import audit
from provenance.pipeline import analyze

load_dotenv()

app = Flask(__name__)
audit.init_db()

# Rate limiting — see planning.md for the reasoning behind these numbers.
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=[],
    storage_uri="memory://",
)


@app.route("/", methods=["GET"])
def index():
    """Human-friendly landing page so the root URL isn't a bare 404."""
    return jsonify(
        {
            "service": "Provenance Guard",
            "description": "Human vs. AI text attribution backend.",
            "endpoints": {
                "POST /submit": "Classify text. Body: {text, creator_id}. (rate-limited 10/min, 100/day)",
                "POST /appeal": "Contest a classification. Body: {content_id, creator_reasoning}.",
                "GET /log": "Recent audit-log entries. Optional ?limit=N.",
                "GET /health": "Liveness check.",
            },
            "note": "POST endpoints need a JSON body and won't open in a browser — use curl or the scripts in scripts/.",
        }
    )


@app.route("/submit", methods=["POST"])
@limiter.limit("10 per minute;100 per day")
def submit():
    data = request.get_json(silent=True) or {}
    text = (data.get("text") or "").strip()
    creator_id = (data.get("creator_id") or "anonymous").strip()

    if not text:
        return jsonify({"error": "field 'text' is required and must be non-empty"}), 400

    content_id = str(uuid.uuid4())
    result = analyze(text)

    llm_score = (
        result["signals"]["llm"]["ai_probability"]
        if result["signals"]["llm"]["available"]
        else None
    )
    stylometry_score = result["signals"]["stylometry"]["ai_probability"]

    audit.record_classification(
        content_id=content_id,
        creator_id=creator_id,
        attribution=result["attribution"],
        confidence=result["ai_probability"],
        llm_score=llm_score,
        stylometry_score=stylometry_score,
        label_variant=result["label"]["variant"],
        metrics=result["signals"]["stylometry"].get("metrics", {}),
    )

    return jsonify(
        {
            "content_id": content_id,
            "creator_id": creator_id,
            "attribution": result["attribution"],
            "confidence": result["ai_probability"],
            "display_confidence": result["display_confidence"],
            "label": result["label"]["text"],
            "label_variant": result["label"]["variant"],
            "scoring_mode": result["scoring_mode"],
            "signals": {
                "llm": {
                    "available": result["signals"]["llm"]["available"],
                    "ai_probability": llm_score,
                    "reasoning": result["signals"]["llm"]["reasoning"],
                },
                "stylometry": {
                    "ai_probability": stylometry_score,
                    "metrics": result["signals"]["stylometry"].get("metrics", {}),
                },
            },
            "status": "classified",
        }
    )


@app.route("/appeal", methods=["POST"])
def appeal():
    data = request.get_json(silent=True) or {}
    content_id = (data.get("content_id") or "").strip()
    creator_reasoning = (data.get("creator_reasoning") or "").strip()

    if not content_id or not creator_reasoning:
        return (
            jsonify(
                {"error": "fields 'content_id' and 'creator_reasoning' are required"}
            ),
            400,
        )

    original = audit.record_appeal(
        content_id=content_id, creator_reasoning=creator_reasoning
    )
    if original is None:
        return jsonify({"error": f"unknown content_id: {content_id}"}), 404

    return jsonify(
        {
            "content_id": content_id,
            "status": "under_review",
            "original_attribution": original["attribution"],
            "original_confidence": original["confidence"],
            "message": (
                "Appeal received. This content's status is now 'under_review' and your "
                "reasoning has been logged for a human reviewer. No automated "
                "re-classification is performed."
            ),
        }
    )


@app.route("/log", methods=["GET"])
def log():
    limit = request.args.get("limit", default=50, type=int)
    return jsonify({"entries": audit.get_log(limit=limit)})


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


@app.errorhandler(404)
def not_found_handler(e):
    return (
        jsonify(
            {
                "error": "not found",
                "hint": "Valid routes: GET /, POST /submit, POST /appeal, GET /log, GET /health.",
            }
        ),
        404,
    )


@app.errorhandler(405)
def method_not_allowed_handler(e):
    return (
        jsonify(
            {
                "error": "method not allowed",
                "hint": "/submit and /appeal require POST with a JSON body, not a browser GET.",
            }
        ),
        405,
    )


@app.errorhandler(429)
def ratelimit_handler(e):
    return (
        jsonify(
            {
                "error": "rate limit exceeded",
                "detail": str(e.description),
                "hint": "Submission is limited to 10/minute, 100/day per client.",
            }
        ),
        429,
    )


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
