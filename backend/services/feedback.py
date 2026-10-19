"""
Advice Memory & Outcome Feedback Loop (Feature 12).

Chronological timeline; confirm/dismiss/correct insights;
track improvement over time without false causality.
"""
from __future__ import annotations

from typing import Any

from analytics.portfolio import DataStore, investor_snapshot
from domain.evidence import ConfidenceLevel, envelope
from domain.persistence import add_feedback, load_feedback
from services.advice_outcome import advice_outcome_report


def timeline(store: DataStore, investor_id: str) -> dict[str, Any]:
    snap = investor_snapshot(store, investor_id)
    if snap.get("error"):
        return {"error": snap["error"], "investor_id": investor_id}

    events: list[dict[str, Any]] = []

    for a in snap.get("advice_history") or []:
        events.append(
            {
                "ts": str(a.get("advice_date")),
                "type": "advice",
                "title": a.get("recommendation"),
                "status": a.get("follow_up_status"),
                "ref": a.get("advice_id"),
            }
        )

    for n in snap.get("notes") or []:
        events.append(
            {
                "ts": str(n.get("created_at", ""))[:10],
                "type": "note",
                "title": (n.get("note_text") or "")[:120],
                "status": n.get("source"),
                "ref": n.get("note_id"),
            }
        )

    ao = advice_outcome_report(store, investor_id)
    for item in ao.get("items") or []:
        events.append(
            {
                "ts": str(item.get("advice_date")),
                "type": "outcome_check",
                "title": item.get("outcome_status"),
                "status": item.get("evidence", {}).get("confidence"),
                "ref": item.get("advice_id"),
            }
        )

    for fb in load_feedback():
        if fb.get("investor_id") == investor_id:
            events.append(
                {
                    "ts": str(fb.get("created_at", ""))[:10],
                    "type": "advisor_feedback",
                    "title": f"{fb.get('action')}: {fb.get('insight_ref', '')}",
                    "status": fb.get("action"),
                    "ref": fb.get("id"),
                    "correction": fb.get("correction"),
                }
            )

    events.sort(key=lambda e: e.get("ts") or "")

    # Improvement tracking — descriptive only, no causal claim
    feedbacks = [f for f in load_feedback() if f.get("investor_id") == investor_id]
    confirmed = sum(1 for f in feedbacks if f.get("action") == "confirm")
    dismissed = sum(1 for f in feedbacks if f.get("action") == "dismiss")
    corrected = sum(1 for f in feedbacks if f.get("action") == "correct")

    return {
        "investor_id": investor_id,
        "events": events,
        "feedback_stats": {
            "confirmed": confirmed,
            "dismissed": dismissed,
            "corrected": corrected,
            "total": len(feedbacks),
        },
        "improvement_note": (
            "Counts reflect advisor labeling of insight quality over time. "
            "They do NOT prove that the system caused client outcome changes."
        ),
        "evidence": envelope(
            "Chronological advice/outcome/feedback timeline",
            confidence=ConfidenceLevel.LIMITED,
            evidence=[{"source": "feedback_loop", "detail": f"{len(events)} events"}],
            limitations=["No causal attribution from timeline alone."],
        ),
        "is_demo": True,
    }


def record_feedback(
    investor_id: str,
    insight_ref: str,
    action: str,
    *,
    correction: str | None = None,
    note: str | None = None,
) -> dict[str, Any]:
    if action not in {"confirm", "dismiss", "correct"}:
        raise ValueError("action must be confirm|dismiss|correct")
    if action == "correct" and not correction:
        raise ValueError("correction text required when action=correct")
    return add_feedback(
        {
            "investor_id": investor_id,
            "insight_ref": insight_ref,
            "action": action,
            "correction": correction,
            "note": note,
        }
    )
