"""End-to-end smoke test using Flask's test client (no live server needed).

Exercises /submit, /appeal, /log, the rate limiter (expects 200s then 429s), and the
three-label reachability of the scoring layer. Run from repo root:

    python scripts/e2e_test.py
"""
from __future__ import annotations

import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except AttributeError:
    pass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Use a throwaway DB so the test doesn't pollute the real audit log.
os.environ["PROVENANCE_DB"] = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "_e2e_test.sqlite3"
)
if os.path.exists(os.environ["PROVENANCE_DB"]):
    os.remove(os.environ["PROVENANCE_DB"])

from app import app  # noqa: E402
from provenance.labels import build_label  # noqa: E402
from provenance.scoring import combine_signals  # noqa: E402

client = app.test_client()

AI_TEXT = (
    "Artificial intelligence represents a transformative paradigm shift in modern "
    "society. It is important to note that the benefits are numerous and varied. "
    "Furthermore, stakeholders must collaborate to ensure responsible deployment."
)
HUMAN_TEXT = (
    "ok so i finally tried that ramen place and honestly? underwhelming. the broth was "
    "fine but WAY too salty and i was thirsty for hours. won't go back tbh"
)

print("=" * 70)
print("1) POST /submit  (two inputs)")
r1 = client.post("/submit", json={"text": AI_TEXT, "creator_id": "user-ai"})
d1 = r1.get_json()
print(f"   AI-ish input   -> {r1.status_code} attribution={d1['attribution']} "
      f"confidence={d1['confidence']} variant={d1['label_variant']}")
print(f"   label: {d1['label']}")

r2 = client.post("/submit", json={"text": HUMAN_TEXT, "creator_id": "user-human"})
d2 = r2.get_json()
print(f"   human input    -> {r2.status_code} attribution={d2['attribution']} "
      f"confidence={d2['confidence']} variant={d2['label_variant']}")
print(f"   label: {d2['label']}")

content_id = d1["content_id"]
print(f"\n   captured content_id for appeal: {content_id}")

print("\n" + "=" * 70)
print("2) Three label variants are reachable (scoring + label layer)")
for p in (0.05, 0.50, 0.95):
    scored = combine_signals(p_llm=p, p_sty=p)
    label = build_label(scored["attribution"], scored["ai_probability"],
                        scored["display_confidence"])
    print(f"   p={p:>4}  -> {scored['attribution']:<13} variant={label['variant']}")
    print(f"            {label['text']}")

print("\n" + "=" * 70)
print("3) POST /appeal")
ra = client.post("/appeal", json={
    "content_id": content_id,
    "creator_reasoning": "I wrote this myself over several weeks; it is not AI output.",
})
da = ra.get_json()
print(f"   -> {ra.status_code} status={da.get('status')} msg={da.get('message')[:60]}...")

print("\n" + "=" * 70)
print("4) GET /log  (most recent entries)")
rl = client.get("/log")
entries = rl.get_json()["entries"]
print(f"   {len(entries)} entries returned. Top entry event_type="
      f"{entries[0].get('event_type')} status={entries[0].get('status')}")

print("\n" + "=" * 70)
print("5) Rate limiting on /submit (limit is 10/min; send 12)")
codes = []
for _ in range(12):
    rr = client.post("/submit", json={"text": HUMAN_TEXT, "creator_id": "flooder"})
    codes.append(rr.status_code)
print(f"   status codes: {codes}")
print(f"   200s: {codes.count(200)}   429s: {codes.count(429)}")

# Clean up throwaway DB. On Windows the SQLite handle may linger; ignore if locked.
import gc  # noqa: E402
import os as _os  # noqa: E402

gc.collect()
try:
    if _os.path.exists(_os.environ["PROVENANCE_DB"]):
        _os.remove(_os.environ["PROVENANCE_DB"])
except OSError:
    pass  # file still locked by the connection pool — harmless for a test artifact
print("\nDONE.")
