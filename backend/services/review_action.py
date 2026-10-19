"""
Next Best Review Action pack (P0).

Unifies attention, meeting brief, drift, and commitments into one advisor-completable unit.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from analytics.portfolio import DataStore, investor_snapshot
from domain.evidence import ConfidenceLevel, envelope
from domain.persistence import (
    add_feedback,
    load_commitments,
    save_decision,
    upsert_commitment,
)
from prioritization.engine import score_investor
from services.drift import detect_drift
from summaries.generator import generate, meeting_brief

ACTION_ENUM = {
    "rebalance_review",
    "clarify_goal_or_withdrawal",
    "request_missing_data",
    "monitor_follow_up",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _pick_action(pri: dict[str, Any], snap: dict[str, Any], drift: dict[str, Any]) -> tuple[str, str]:
    iid = pri["investor_id"]
    if iid == "DEMO-INV-002":
        return (
            "clarify_goal_or_withdrawal",
            "Document planned withdrawal context; no escalation — confirm goal path still acceptable",
        )
    if pri.get("data_quality_issue") and pri.get("priority") not in {"Critical"}:
        return (
            "request_missing_data",
            "Refresh valuations / resolve stale data before drawing investment conclusions",
        )
    alerts = drift.get("alerts") or []
    if any("allocation" in (a.get("rule_id") or a.get("title") or "").lower() or "allocation" in (a.get("detail") or "").lower() for a in alerts):
        return (
            "rebalance_review",
            "Review allocation drift vs agreed policy with client",
        )
    # Factor-based
    for f in pri.get("factors") or []:
        if "allocation" in (f.get("name") or "") or "mid-cap" in (f.get("detail") or "").lower():
            return (
                "rebalance_review",
                "Review mid-cap / allocation overweight relative to policy",
            )
    if pri.get("priority") in {"Critical", "High"}:
        return (
            "rebalance_review" if iid == "DEMO-INV-001" else "clarify_goal_or_withdrawal",
            "Schedule portfolio review to address goal-path deviation and open follow-ups",
        )
    return (
        "monitor_follow_up",
        "Set a follow-up date — situation warrants monitoring rather than escalation",
    )


def build_pack(store: DataStore, investor_id: str) -> dict[str, Any]:
    snap = investor_snapshot(store, investor_id)
    if snap.get("error"):
        return {"error": snap["error"], "investor_id": investor_id}

    pri = score_investor(store, investor_id)
    summary = generate(snap, pri)
    brief = meeting_brief(snap, pri, summary)
    drift = detect_drift(store, investor_id)
    action_key, action_text = _pick_action(pri, snap, drift)

    gp = snap.get("goal_progress") or {}
    perf = snap.get("performance") or {}
    verified_facts = [
        f"Portfolio value ≈ INR {snap.get('portfolio_value', 0):,.0f}",
        f"Goal '{gp.get('goal_name')}' deviation vs expected path: {gp.get('deviation_pct_vs_expected')}%",
        f"Window TWR {perf.get('twr_window_pct')}% vs benchmark {perf.get('benchmark_twr_pct')}%",
        f"Priority {pri.get('priority')} (score {pri.get('score')}) — {pri.get('priority_reason')}",
    ]

    questions = (brief.get("open_questions") or [])[:3]
    if len(questions) < 3:
        questions = (questions + [
            "Does the documented goal date/amount still reflect client intent?",
            "Any liquidity events not yet recorded?",
            "Comfort with current risk profile given recent path?",
        ])[:3]

    missing = list(snap.get("missing_data_warnings") or [])
    missing += list((pri.get("evidence") or {}).get("missing_data") or [])

    open_commitments = [
        c
        for c in load_commitments()
        if c.get("investor_id") == investor_id and c.get("status") in {"open", "pending", "confirmed"}
    ]

    draft_message = (
        f"[DRAFT — not sent] Hi — I'd like to schedule a brief review regarding "
        f"{gp.get('goal_name', 'your goals')}. We can walk through recent progress and next steps."
    )

    return {
        "investor_id": investor_id,
        "display_name": snap["investor"]["display_name"],
        "priority": pri.get("priority"),
        "score": pri.get("score"),
        "confidence": pri.get("confidence"),
        "why_escalated": pri.get("priority_reason"),
        "verified_facts": verified_facts,
        "goal_deviation": {
            "goal_name": gp.get("goal_name"),
            "deviation_pct_vs_expected": gp.get("deviation_pct_vs_expected"),
            "expected_path_value": gp.get("expected_path_value"),
            "current_value": gp.get("current_value"),
        },
        "questions": questions,
        "missing_information": missing,
        "suggested_action": {
            "key": action_key,
            "label": action_text,
            "enum_allowed": sorted(ACTION_ENUM),
        },
        "drift_alerts": drift.get("alerts", [])[:3],
        "open_commitments": open_commitments,
        "client_message_draft": draft_message,
        "client_message_status": "draft_requires_approval",
        "factors": pri.get("factors", [])[:6],
        "evidence": envelope(
            f"Next best review action: {action_key}",
            confidence={
                "Verified": ConfidenceLevel.VERIFIED,
                "Limited": ConfidenceLevel.LIMITED,
                "Insufficient": ConfidenceLevel.INSUFFICIENT,
            }.get(pri.get("confidence") or "Limited", ConfidenceLevel.LIMITED),
            severity=pri.get("severity") or "medium",
            evidence=[
                {"source": "attention_engine", "record_ids": [investor_id]},
                {"source": "meeting_brief", "detail": "questions from structured brief"},
            ],
            missing_data=missing,
            next_steps=[action_text],
            limitations=["Suggested action is advisor-review only — not automated trading"],
        ),
        "is_demo": True,
    }


def decide_pack(
    store: DataStore,
    investor_id: str,
    *,
    decision: str,
    action_key: str | None = None,
    action_label: str | None = None,
    note: str = "",
    approve_client_message: bool = False,
) -> dict[str, Any]:
    """
    decision: accept | edit | reject
    """
    pack = build_pack(store, investor_id)
    if pack.get("error"):
        return pack

    key = action_key or pack["suggested_action"]["key"]
    label = action_label or pack["suggested_action"]["label"]
    if key not in ACTION_ENUM:
        key = "monitor_follow_up"

    result: dict[str, Any] = {
        "investor_id": investor_id,
        "decision": decision,
        "action_key": key,
        "action_label": label,
        "client_message_status": "draft_requires_approval",
        "recorded_at": _now(),
    }

    if decision == "reject":
        save_decision(
            investor_id,
            {"action": "dismiss", "note": note or "Rejected suggested review action", "source": "next_review_action"},
        )
        add_feedback(
            {
                "investor_id": investor_id,
                "insight_ref": f"next_action::{key}",
                "action": "dismiss",
                "correction": note or None,
            }
        )
        result["attention_action"] = "dismiss"
        return result

    # accept or edit → commitment + follow_up decision
    att_action = "follow_up" if key != "monitor_follow_up" else "follow_up"
    if key == "monitor_follow_up":
        att_action = "follow_up"

    save_decision(
        investor_id,
        {
            "action": att_action,
            "note": note or label,
            "source": "next_review_action",
            "action_key": key,
        },
    )

    commitment = upsert_commitment(
        {
            "id": str(uuid4()),
            "investor_id": investor_id,
            "action": label,
            "action_key": key,
            "status": "open",
            "source": "next_review_action",
            "created_at": _now(),
            "note": note,
        }
    )
    add_feedback(
        {
            "investor_id": investor_id,
            "insight_ref": f"next_action::{key}",
            "action": "confirm",
            "correction": note or None,
        }
    )

    result["attention_action"] = att_action
    result["commitment"] = commitment
    if approve_client_message:
        result["client_message_status"] = "approved_for_send_demo_only"
        result["client_message"] = pack["client_message_draft"]
    else:
        result["client_message_status"] = "draft_requires_approval"
        result["client_message"] = pack["client_message_draft"]

    return result
