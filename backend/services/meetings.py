"""
AI Meeting Prep & Follow-Through (Feature 10).

Pre-meeting pack; post-meeting draft actions needing confirmation; track commitments.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from analytics.portfolio import DataStore, investor_snapshot
from domain.evidence import ConfidenceLevel, envelope
from domain.persistence import load_commitments, upsert_commitment
from prioritization.engine import score_investor
from services.client_summary import build_structured_summary
from services.drift import detect_drift
from summaries.generator import generate, meeting_brief


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def pre_meeting_pack(store: DataStore, investor_id: str) -> dict[str, Any]:
    snap = investor_snapshot(store, investor_id)
    if snap.get("error"):
        return {"error": snap["error"], "investor_id": investor_id}

    pri = score_investor(store, investor_id)
    summary = generate(snap, pri)
    brief = meeting_brief(snap, pri, summary)
    structured = build_structured_summary(store, investor_id)
    drift = detect_drift(store, investor_id)
    open_commitments = [
        c
        for c in load_commitments()
        if c.get("investor_id") == investor_id and c.get("status") in {"open", "pending", "confirmed"}
    ]

    return {
        "investor_id": investor_id,
        "display_name": snap["investor"]["display_name"],
        "priority": pri,
        "brief": brief,
        "structured_highlights": [
            {"id": p["id"], "title": p["title"], "summary": p["summary"]} for p in structured["parts"]
        ],
        "drift_alerts": drift.get("alerts", []),
        "open_commitments": open_commitments,
        "agenda": brief.get("suggested_discussion_points", []),
        "evidence": envelope(
            "Pre-meeting pack from structured analytics",
            confidence=ConfidenceLevel.VERIFIED,
            evidence=[{"source": "meeting_prep", "record_ids": [investor_id]}],
            limitations=brief.get("limitations", []),
        ),
        "is_demo": True,
    }


def draft_post_meeting_actions(
    store: DataStore,
    investor_id: str,
    notes_text: str,
) -> dict[str, Any]:
    """Draft actions from free text — require confirmation before authoritative."""
    lower = notes_text.lower()
    drafts: list[dict[str, Any]] = []

    def add(action: str, kind: str):
        drafts.append(
            {
                "draft_id": str(uuid4()),
                "investor_id": investor_id,
                "action": action,
                "kind": kind,
                "status": "pending_confirmation",
                "authoritative": False,
                "created_at": _now(),
            }
        )

    if "rebalanc" in lower:
        add("Prepare rebalancing proposal for next review", "portfolio")
    if "sip" in lower:
        add("Document SIP change discussion and client decision", "funding")
    if "follow" in lower:
        add("Schedule follow-up meeting", "relationship")
    if "risk" in lower:
        add("Update risk-profile acknowledgment if client confirmed change", "compliance")
    if not drafts:
        add("File meeting notes and mark review complete", "admin")

    return {
        "investor_id": investor_id,
        "drafts": drafts,
        "note": "Drafts are NOT authoritative until confirmed.",
        "evidence": envelope(
            f"{len(drafts)} draft post-meeting actions",
            confidence=ConfidenceLevel.LIMITED,
            evidence=[{"source": "post_meeting_draft", "detail": "Heuristic extraction from notes"}],
            next_steps=["Confirm each draft to create tracked commitments."],
        ),
        "is_demo": True,
    }


def confirm_commitment(
    investor_id: str,
    action: str,
    *,
    due: str | None = None,
    commitment_id: str | None = None,
    status: str = "open",
) -> dict[str, Any]:
    return upsert_commitment(
        {
            "id": commitment_id,
            "investor_id": investor_id,
            "action": action,
            "due": due,
            "status": status,
            "source": "meeting_follow_through",
            "authoritative": True,
        }
    )


def list_commitments(investor_id: str | None = None) -> dict[str, Any]:
    items = load_commitments()
    if investor_id:
        items = [c for c in items if c.get("investor_id") == investor_id]
    return {"commitments": items, "is_demo": True}
