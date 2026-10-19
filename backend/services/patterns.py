"""
Cross-Client Pattern Discovery (Feature 9).

Explainable cohorts with counts and drill-down to clients.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any

from analytics.portfolio import DataStore, allocation, goal_progress
from domain.evidence import ConfidenceLevel, envelope
from prioritization.engine import rank_book


def discover_patterns(store: DataStore) -> dict[str, Any]:
    ranked = rank_book(store)
    by_id = {r["investor_id"]: r for r in ranked}

    cohorts: list[dict[str, Any]] = []

    # Cohort: behind goal path
    behind = [r for r in ranked if r.get("goal_status", {}).get("deviation_pct_vs_expected", 0) <= -8]
    cohorts.append(
        _cohort(
            "goal_behind_8pct",
            "Behind expected path by ≥8%",
            behind,
            "goal_status.deviation_pct_vs_expected <= -8",
            "Clients whose mapped goal value is at least 8% below the documented expected path.",
        )
    )

    # Cohort: Critical priority
    critical = [r for r in ranked if r["priority"] == "Critical"]
    cohorts.append(
        _cohort(
            "priority_critical",
            "Critical priority",
            critical,
            "priority == Critical",
            "Attention score ≥70 under configured weights (or demo narrative floor).",
        )
    )

    # Cohort: overdue follow-ups
    overdue_ids = set()
    for _, a in store.advice.iterrows():
        if a.get("follow_up_status") == "overdue":
            overdue_ids.add(str(a["investor_id"]))
    overdue = [by_id[i] for i in overdue_ids if i in by_id]
    cohorts.append(
        _cohort(
            "overdue_followups",
            "Overdue advice follow-ups",
            overdue,
            "advice.follow_up_status == overdue",
            "At least one advice row with follow_up_status=overdue.",
        )
    )

    # Cohort: mid-cap overweight ≥5pp
    mid_over: list[dict[str, Any]] = []
    for iid in store.investors["investor_id"].tolist():
        h = store.holdings[store.holdings["investor_id"] == iid]
        if h.empty:
            continue
        alloc = {a["asset_class"]: a["weight_pct"] for a in allocation(h)}
        mid = alloc.get("Equity - Mid Cap", 0)
        if mid >= 20:  # policy 15 + 5
            row = by_id.get(str(iid))
            if row:
                mid_over.append({**row, "mid_cap_weight_pct": mid})
    cohorts.append(
        _cohort(
            "midcap_overweight",
            "Mid-cap overweight (≥20%)",
            mid_over,
            "Equity - Mid Cap weight >= 20 (policy 15 + 5pp)",
            "Holdings weight for mid-cap sleeve at least 5pp above moderate policy.",
        )
    )

    # Cohort: stale data
    stale = [r for r in ranked if r.get("data_quality_issue")]
    cohorts.append(
        _cohort(
            "stale_data",
            "Stale / missing valuation data",
            stale,
            "data_freshness_days >= 45 or missing",
            "Data-quality cohort — not automatic financial distress.",
            distress=False,
        )
    )

    # Cohort: long-tail High/Critical
    long_tail_hot = [r for r in ranked if r["tier"] == "long_tail" and r["priority"] in {"Critical", "High"}]
    cohorts.append(
        _cohort(
            "long_tail_attention",
            "Long-tail clients needing review",
            long_tail_hot,
            "tier == long_tail AND priority in {Critical, High}",
            "Surfaces clients outside daily high-visibility attention.",
        )
    )

    return {
        "cohorts": cohorts,
        "total_clients": len(ranked),
        "evidence": envelope(
            f"{len(cohorts)} explainable cohorts over {len(ranked)} DEMO clients",
            confidence=ConfidenceLevel.VERIFIED,
            evidence=[{"source": "pattern_discovery", "detail": c["id"]} for c in cohorts],
            limitations=["Cohorts are rule-based; not causal claims."],
        ),
        "is_demo": True,
    }


def _cohort(
    cid: str,
    title: str,
    members: list[dict[str, Any]],
    rule: str,
    explanation: str,
    distress: bool = True,
) -> dict[str, Any]:
    return {
        "id": cid,
        "title": title,
        "count": len(members),
        "rule": rule,
        "explanation": explanation,
        "is_distress_signal": distress,
        "clients": [
            {
                "investor_id": m["investor_id"],
                "display_name": m["display_name"],
                "priority": m["priority"],
                "score": m["score"],
                "tier": m["tier"],
                "goal_deviation": m.get("goal_status", {}).get("deviation_pct_vs_expected"),
                **{k: m[k] for k in ("mid_cap_weight_pct",) if k in m},
            }
            for m in members[:40]
        ],
        "truncated": len(members) > 40,
    }


def cohort_detail(store: DataStore, cohort_id: str) -> dict[str, Any]:
    patterns = discover_patterns(store)
    for c in patterns["cohorts"]:
        if c["id"] == cohort_id:
            return {**c, "is_demo": True}
    return {"error": "Cohort not found", "cohort_id": cohort_id}
