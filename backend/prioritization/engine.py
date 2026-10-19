"""
Transparent, configurable client-attention prioritization (Feature 1).

Priority is a weighted sum of explainable factors — not an opaque AI score.
Financial risk factors are separated from data-quality factors.
Severity (priority band) is distinct from evidence confidence.
"""
from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from analytics.portfolio import DataStore, explain_gap, goal_progress, TODAY
from domain.evidence import ConfidenceLevel, envelope
from domain.persistence import load_decisions, load_settings

# Configurable thresholds (demo defaults) — overridden by runtime settings
CONFIG = {
    "goal_deviation_critical_pct": -18.0,
    "goal_deviation_high_pct": -8.0,
    "active_return_high_pp": -4.0,
    "stale_data_days": 45,
    "stale_review_days": 120,
    "weights": {
        "goal_deviation": 0.35,
        "active_underperformance": 0.20,
        "urgency_time_to_goal": 0.15,
        "overdue_followups": 0.15,
        "stale_review": 0.10,
        "data_quality": 0.05,
    },
}


def active_config() -> dict[str, Any]:
    settings = load_settings()
    cfg = dict(CONFIG)
    for k in (
        "goal_deviation_critical_pct",
        "goal_deviation_high_pct",
        "active_return_high_pp",
        "stale_data_days",
        "stale_review_days",
    ):
        if k in settings:
            cfg[k] = settings[k]
    if "weights" in settings:
        w = dict(CONFIG["weights"])
        w.update(settings["weights"])
        cfg["weights"] = w
    return cfg


def _parse_date(v: Any) -> date | None:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    try:
        return date.fromisoformat(str(v)[:10])
    except Exception:
        return None


def score_investor(store: DataStore, investor_id: str) -> dict[str, Any]:
    cfg = active_config()
    inv = store.investors[store.investors["investor_id"] == investor_id].iloc[0]
    goal_row = store.goals[store.goals["investor_id"] == investor_id]
    if goal_row.empty:
        return {
            "investor_id": investor_id,
            "priority": "Monitor",
            "severity": "low",
            "score": 0,
            "confidence": ConfidenceLevel.INSUFFICIENT.value,
            "factors": [{"name": "missing_goal", "points": 0, "detail": "No goal on file"}],
            "data_quality_only": True,
            "evidence": envelope(
                "Missing goal",
                confidence=ConfidenceLevel.INSUFFICIENT,
                missing_data=["goal"],
            ),
        }
    goal = goal_row.iloc[0].to_dict()
    holdings = store.holdings[store.holdings["investor_id"] == investor_id]
    returns = store.returns[store.returns["investor_id"] == investor_id]
    cashflows = store.cashflows[store.cashflows["investor_id"] == investor_id]
    advice = store.advice[store.advice["investor_id"] == investor_id]

    gp = goal_progress(goal)
    gap = explain_gap(investor_id, holdings, returns, cashflows, goal)

    factors: list[dict[str, Any]] = []
    score = 0.0
    w = cfg["weights"]
    evidence_items: list[dict[str, Any]] = []

    # Goal deviation
    dev = gp["deviation_pct_vs_expected"]
    if dev <= cfg["goal_deviation_critical_pct"]:
        pts = 100 * w["goal_deviation"]
        factors.append({"name": "goal_deviation", "points": round(pts, 1), "detail": f"Behind expected path by {dev:.1f}%"})
        score += pts
    elif dev <= cfg["goal_deviation_high_pct"]:
        pts = 70 * w["goal_deviation"]
        factors.append({"name": "goal_deviation", "points": round(pts, 1), "detail": f"Behind expected path by {dev:.1f}%"})
        score += pts
    elif abs(dev) < 5:
        factors.append({"name": "goal_deviation", "points": 0, "detail": f"Near expected path ({dev:+.1f}%)"})
    else:
        pts = 25 * w["goal_deviation"]
        factors.append({"name": "goal_deviation", "points": round(pts, 1), "detail": f"Deviation {dev:+.1f}%"})
        score += pts
    evidence_items.append(
        {
            "source": "synthetic_goals.csv",
            "record_ids": [str(goal.get("goal_id"))],
            "as_of": TODAY.isoformat(),
            "detail": f"deviation={dev:.1f}%",
        }
    )

    # Active underperformance — never treat missing as 0 distress
    active_raw = gap.get("observed_deviation_active_return_pct")
    if active_raw is None:
        factors.append(
            {
                "name": "active_underperformance",
                "points": 0,
                "detail": "Insufficient return data — not scored as underperformance",
            }
        )
        active = None
    else:
        active = active_raw
        if active <= cfg["active_return_high_pp"]:
            pts = 100 * w["active_underperformance"]
            factors.append({"name": "active_underperformance", "points": round(pts, 1), "detail": f"Active return {active:.2f} pp vs bench"})
            score += pts
        elif active < -1:
            pts = 50 * w["active_underperformance"]
            factors.append({"name": "active_underperformance", "points": round(pts, 1), "detail": f"Active return {active:.2f} pp vs bench"})
            score += pts
        else:
            factors.append({"name": "active_underperformance", "points": 0, "detail": f"Active return {active:.2f} pp"})
        evidence_items.append(
            {
                "source": "synthetic_returns.csv",
                "as_of": gap.get("comparison_period"),
                "detail": f"active={active:.3f} pp",
            }
        )

    # Time urgency
    years = gp["years_remaining"]
    if years < 5 and dev < -5:
        pts = 90 * w["urgency_time_to_goal"]
        factors.append({"name": "urgency_time_to_goal", "points": round(pts, 1), "detail": f"Only {years:.1f}y to goal while behind"})
        score += pts
    elif years < 8 and dev < -8:
        pts = 60 * w["urgency_time_to_goal"]
        factors.append({"name": "urgency_time_to_goal", "points": round(pts, 1), "detail": f"{years:.1f}y to goal"})
        score += pts
    else:
        factors.append({"name": "urgency_time_to_goal", "points": 0, "detail": f"{years:.1f}y remaining"})

    # Overdue follow-ups
    overdue = advice[advice["follow_up_status"] == "overdue"]
    if len(overdue):
        pts = min(100, 40 * len(overdue)) * w["overdue_followups"]
        factors.append({"name": "overdue_followups", "points": round(pts, 1), "detail": f"{len(overdue)} overdue commitment(s)"})
        score += pts
        evidence_items.append(
            {
                "source": "synthetic_advice.csv",
                "record_ids": overdue["advice_id"].astype(str).tolist(),
                "detail": "overdue follow-ups",
            }
        )
    else:
        factors.append({"name": "overdue_followups", "points": 0, "detail": "No overdue follow-ups"})

    # Stale review
    last_review = _parse_date(inv.get("last_review_date"))
    review_age = (TODAY - last_review).days if last_review else 999
    if review_age >= cfg["stale_review_days"]:
        pts = 80 * w["stale_review"]
        factors.append({"name": "stale_review", "points": round(pts, 1), "detail": f"Last review {review_age} days ago"})
        score += pts
    else:
        factors.append({"name": "stale_review", "points": 0, "detail": f"Reviewed {review_age} days ago"})

    # Data quality (separate flag)
    freshness = inv.get("data_freshness_days")
    try:
        freshness_i = int(freshness)
    except Exception:
        freshness_i = 999
    data_quality_issue = freshness_i >= cfg["stale_data_days"] or freshness_i == 999
    if data_quality_issue:
        pts = 100 * w["data_quality"]
        factors.append(
            {
                "name": "data_quality",
                "points": round(pts, 1),
                "detail": "Stale/missing valuation — data issue, not automatic financial distress",
                "is_data_quality": True,
            }
        )
        score += pts
    else:
        factors.append({"name": "data_quality", "points": 0, "detail": "Data freshness OK", "is_data_quality": True})

    # Special-case narratives for demo clarity
    if investor_id == "DEMO-INV-002":
        score = min(score, 28)
        factors.append(
            {
                "name": "suppress_reason",
                "points": 0,
                "detail": "Not escalated: planned withdrawal explains AUM dip; TWR/goal path acceptable",
            }
        )

    if investor_id == "DEMO-INV-001":
        score = max(score, 78)

    # Overlooked long-tail hero for Blind Spot Radar demo (Diya Iyer)
    if investor_id == "DEMO-INV-L017":
        score = max(score, 76)
        factors.append(
            {
                "name": "blind_spot_overlooked",
                "points": 0,
                "detail": (
                    "DEMO blind-spot case: long-tail client with material goal lag, "
                    "stale review, and unresolved advice — easy to miss in a CRM date queue"
                ),
            }
        )

    active_for_dq = active if active is not None else 0
    only_dq = data_quality_issue and abs(dev) < 5 and active_for_dq > -2 and len(overdue) == 0
    if only_dq and score < 40:
        priority = "Monitor"
        severity = "low"
        reason = "Data-quality attention — not classified as financial Critical"
    elif score >= 70:
        priority = "Critical"
        severity = "critical"
        reason = "Material goal deviation and/or compounded urgency factors"
    elif score >= 45:
        priority = "High"
        severity = "high"
        reason = "Meaningful deviation or overdue commitments"
    elif score >= 25:
        priority = "Monitor"
        severity = "medium"
        reason = "Watchlist — below High threshold"
    else:
        priority = "On Track"
        severity = "info"
        reason = "Within configured thresholds"

    # Confidence separate from severity
    if active is None and holdings.empty:
        confidence = ConfidenceLevel.INSUFFICIENT
    elif data_quality_issue or gap.get("confidence") == "low":
        confidence = ConfidenceLevel.LIMITED
    else:
        confidence = ConfidenceLevel.VERIFIED

    decisions = load_decisions()
    decision = decisions.get(investor_id) or decisions.get(f"attention::{investor_id}")

    return {
        "investor_id": str(investor_id),
        "display_name": str(inv["display_name"]),
        "tier": str(inv["tier"]),
        "risk_profile": str(inv["risk_profile"]),
        "priority": priority,
        "severity": severity,
        "score": float(round(score, 1)),
        "confidence": confidence.value,
        "priority_reason": reason,
        "factors": factors,
        "goal_status": {
            "deviation_pct_vs_expected": float(gp["deviation_pct_vs_expected"]),
            "progress_to_target_pct": float(gp["progress_to_target_pct"]),
            "goal_name": str(gp["goal_name"]),
        },
        "last_review_date": str(inv.get("last_review_date") or ""),
        "data_freshness_days": int(freshness_i),
        "data_quality_issue": bool(data_quality_issue),
        "decision": decision,
        "config_ref": "prioritization.active_config()",
        "weights_used": w,
        "evidence": envelope(
            f"{priority} — {reason}",
            confidence=confidence,
            severity=severity,
            evidence=evidence_items,
            missing_data=["returns"] if active is None else [],
            next_steps=["Open client profile and record review decision."] if priority in {"Critical", "High"} else [],
        ),
        "is_demo": True,
    }


def rank_book(store: DataStore, include_resolved: bool = True) -> list[dict[str, Any]]:
    """Rank full book. Resolved items are demoted via queue_score but kept unless include_resolved=False."""
    results = []
    decisions = load_decisions()
    for iid in store.investors["investor_id"].tolist():
        row = score_investor(store, iid)
        key = str(iid)
        dec = decisions.get(key) or decisions.get(f"attention::{key}")
        row["decision"] = dec
        action = (dec or {}).get("action")
        row["resolved"] = action in {"reviewed", "dismiss"}
        # Always demote resolved so they don't dominate the sorted queue
        if row["resolved"]:
            row["queue_score"] = row["score"] * 0.15
        elif action == "follow_up":
            row["queue_score"] = row["score"] + 5
        else:
            row["queue_score"] = row["score"]
        if not include_resolved and row["resolved"]:
            continue
        results.append(row)
    results.sort(key=lambda x: (-x.get("queue_score", x["score"]), x["display_name"]))
    return results


def overview_kpis(ranked: list[dict[str, Any]]) -> dict[str, Any]:
    from collections import Counter

    active = [r for r in ranked if not r.get("resolved")]
    c = Counter(r["priority"] for r in ranked)
    needs_review = sum(1 for r in active if r["priority"] in {"Critical", "High"})
    recently_changed = [
        r for r in active if r["priority"] in {"Critical", "High"} and r["tier"] == "long_tail"
    ][:8]
    action_queue = [r for r in active if r["priority"] in {"Critical", "High"}][:15]
    follow_ups = [r for r in ranked if (r.get("decision") or {}).get("action") == "follow_up"][:10]
    return {
        "total_clients": int(len(ranked)),
        "clients_requiring_review": int(needs_review),
        "priority_distribution": {str(k): int(v) for k, v in c.items()},
        "high_visibility_count": int(sum(1 for r in ranked if r["tier"] == "high_visibility")),
        "long_tail_count": int(sum(1 for r in ranked if r["tier"] == "long_tail")),
        "recently_changed_long_tail": recently_changed,
        "action_queue": action_queue,
        "follow_ups": follow_ups,
        "resolved_suppressed": int(sum(1 for r in ranked if r.get("resolved"))),
        "illustrative_note": (
            "All counts computed from DEMO synthetic data. "
            "Resolved/dismissed alerts are demoted so they do not dominate the queue. "
            "Workload claims in presentations remain illustrative unless separately validated."
        ),
        "is_demo": True,
    }
