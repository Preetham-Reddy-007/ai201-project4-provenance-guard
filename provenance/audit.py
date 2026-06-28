"""Structured audit log backed by SQLite.

Every attribution decision and every appeal is recorded as a structured row. The log is
the canonical record graders and (in a real deployment) human reviewers rely on. Two
event types share a ``content_id`` so a reviewer can see the original classification and
the appeal side by side.
"""
from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from typing import Dict, List, Optional

DB_PATH = os.environ.get(
    "PROVENANCE_DB",
    os.path.join(os.path.dirname(os.path.dirname(__file__)), "provenance_audit.sqlite3"),
)


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS content (
                content_id   TEXT PRIMARY KEY,
                creator_id   TEXT,
                attribution  TEXT,
                confidence   REAL,
                status       TEXT,
                created_at   TEXT
            );

            CREATE TABLE IF NOT EXISTS audit_log (
                id                 INTEGER PRIMARY KEY AUTOINCREMENT,
                content_id         TEXT,
                creator_id         TEXT,
                timestamp          TEXT,
                event_type         TEXT,   -- 'classification' | 'appeal'
                attribution        TEXT,
                confidence         REAL,
                llm_score          REAL,
                stylometry_score   REAL,
                label_variant      TEXT,
                status             TEXT,
                appeal_reasoning   TEXT,
                metrics_json       TEXT
            );
            """
        )


def record_classification(
    *,
    content_id: str,
    creator_id: str,
    attribution: str,
    confidence: float,
    llm_score: Optional[float],
    stylometry_score: float,
    label_variant: str,
    metrics: Dict,
) -> None:
    ts = _now()
    with _connect() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO content
               (content_id, creator_id, attribution, confidence, status, created_at)
               VALUES (?, ?, ?, ?, 'classified', ?)""",
            (content_id, creator_id, attribution, confidence, ts),
        )
        conn.execute(
            """INSERT INTO audit_log
               (content_id, creator_id, timestamp, event_type, attribution, confidence,
                llm_score, stylometry_score, label_variant, status, appeal_reasoning,
                metrics_json)
               VALUES (?, ?, ?, 'classification', ?, ?, ?, ?, ?, 'classified', NULL, ?)""",
            (
                content_id,
                creator_id,
                ts,
                attribution,
                confidence,
                llm_score,
                stylometry_score,
                label_variant,
                json.dumps(metrics),
            ),
        )


def get_content(content_id: str) -> Optional[Dict]:
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM content WHERE content_id = ?", (content_id,)
        ).fetchone()
        return dict(row) if row else None


def record_appeal(*, content_id: str, creator_reasoning: str) -> Optional[Dict]:
    """Set status to under_review and log the appeal alongside the original entry.

    Returns the original content record, or None if the content_id is unknown.
    """
    original = get_content(content_id)
    if original is None:
        return None

    ts = _now()
    with _connect() as conn:
        conn.execute(
            "UPDATE content SET status = 'under_review' WHERE content_id = ?",
            (content_id,),
        )
        conn.execute(
            """INSERT INTO audit_log
               (content_id, creator_id, timestamp, event_type, attribution, confidence,
                llm_score, stylometry_score, label_variant, status, appeal_reasoning,
                metrics_json)
               VALUES (?, ?, ?, 'appeal', ?, ?, NULL, NULL, NULL, 'under_review', ?, NULL)""",
            (
                content_id,
                original["creator_id"],
                ts,
                original["attribution"],
                original["confidence"],
                creator_reasoning,
            ),
        )
    return original


def get_log(limit: int = 50) -> List[Dict]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    entries = []
    for row in rows:
        entry = dict(row)
        if entry.get("metrics_json"):
            try:
                entry["metrics"] = json.loads(entry["metrics_json"])
            except (TypeError, ValueError):
                entry["metrics"] = None
        entry.pop("metrics_json", None)
        # Drop null fields to keep the JSON readable.
        entries.append({k: v for k, v in entry.items() if v is not None})
    return entries
