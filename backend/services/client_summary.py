"""
Evidence-Backed Dynamic Client Summary (Feature 3).

10-part structured summary with expandable evidence per section.
"""
from __future__ import annotations

from typing import Any

from analytics.portfolio import DataStore, investor_snapshot
from domain.evidence import ConfidenceLevel, envelope, insufficient
from prioritization.engine import score_investor
from services.advice_outcome import advice_outcome_report
from services.drift import detect_drift


PARTS = [
    "identity",
    "goal_position",
    "portfolio_allocation",
    "performance",
    "gap_drivers",
    "advice_outcomes",
    "drift_signals",
    "commitments",
    "data_quality",
    "recommended_actions",
]


def build_structured_summary(store: DataStore, investor_id: str) -> dict[str, Any]:
    snap = investor_snapshot(store, investor_id)
    if snap.get("error"):
        return {"error": snap["error"], "investor_id": investor_id}

    pri = score_investor(store, investor_id)
    ao = advice_outcome_report(store, investor_id)
    drift = detect_drift(store, investor_id)
    inv = snap["investor"]
    gp = snap["goal_progress"]
    perf = snap["performance"]
    gap = snap["gap_explanation"]

    sections: list[dict[str, Any]] = []

    # 1 Identity
    sections.append(
        {
            "id": "identity",
            "title": "Client identity",
            "summary": f"{inv['display_name']} · {inv['tier']} · {inv['risk_profile']} · {inv['city']}",
            "evidence": envelope(
                "Identity from investor master",
                confidence=ConfidenceLevel.VERIFIED,
                evidence=[
                    {
                        "source": "synthetic_investors.csv",
                        "record_ids": [investor_id],
                        "as_of": str(snap["data_timestamps"].get("as_of")),
                        "detail": f"last_review={inv.get('last_review_date')}",
                    }
                ],
            ),
        }
    )

    # 2 Goal position
    sections.append(
        {
            "id": "goal_position",
            "title": "Goal position",
            "summary": (
                f"{gp['goal_name']}: {gp['progress_to_target_pct']:.1f}% of target, "
                f"{gp['deviation_pct_vs_expected']:+.1f}% vs expected path"
            ),
            "metrics": {
                "current_value": gp["current_value"],
                "expected_path_value": gp["expected_path_value"],
                "target_amount": gp["target_amount"],
                "years_remaining": gp["years_remaining"],
            },
            "evidence": envelope(
                "Goal vs documented expected path",
                confidence=ConfidenceLevel.VERIFIED,
                severity="critical" if gp["deviation_pct_vs_expected"] <= -18 else "high" if gp["deviation_pct_vs_expected"] <= -8 else "info",
                evidence=[
                    {
                        "source": "synthetic_goals.csv",
                        "detail": gp["methodology"],
                        "as_of": snap["data_timestamps"]["as_of"],
                    }
                ],
            ),
        }
    )

    # 3 Allocation
    alloc = snap["allocation"]
    alloc_txt = ", ".join(f"{a['asset_class']} {a['weight_pct']:.0f}%" for a in alloc[:4]) or "No holdings"
    sections.append(
        {
            "id": "portfolio_allocation",
            "title": "Portfolio allocation",
            "summary": alloc_txt,
            "allocation": alloc,
            "evidence": envelope(
                "Holdings weights",
                confidence=ConfidenceLevel.VERIFIED if alloc else ConfidenceLevel.INSUFFICIENT,
                evidence=[
                    {
                        "source": "synthetic_holdings.csv",
                        "as_of": str(snap["data_timestamps"].get("holdings_as_of")),
                        "detail": f"{len(alloc)} sleeves",
                    }
                ]
                if alloc
                else [],
                missing_data=[] if alloc else ["holdings"],
            ),
        }
    )

    # 4 Performance
    if perf.get("twr_window_pct") is None:
        perf_ev = insufficient("Performance window", ["returns series"])
        perf_sum = "Insufficient data"
    else:
        perf_sum = (
            f"TWR {perf['twr_window_pct']}% vs bench {perf['benchmark_twr_pct']}% "
            f"(active {perf['active_return_pct']} pp)"
        )
        perf_ev = envelope(
            perf_sum,
            confidence=ConfidenceLevel.VERIFIED if gap.get("confidence") == "medium" else ConfidenceLevel.LIMITED,
            evidence=[{"source": "synthetic_returns.csv", "detail": perf["methodology"]}],
            limitations=gap.get("limitations", []),
        )
    sections.append(
        {
            "id": "performance",
            "title": "Performance vs benchmark",
            "summary": perf_sum,
            "metrics": perf,
            "evidence": perf_ev,
        }
    )

    # 5 Gap drivers
    drivers = gap.get("factors") or []
    sections.append(
        {
            "id": "gap_drivers",
            "title": "Gap drivers",
            "summary": "; ".join(d["factor"] for d in drivers[:3]) or "Insufficient data for drivers",
            "drivers": drivers[:6],
            "evidence": envelope(
                "Qualified driver analysis",
                confidence={
                    "high": ConfidenceLevel.VERIFIED,
                    "medium": ConfidenceLevel.VERIFIED,
                    "low": ConfidenceLevel.LIMITED,
                    "none": ConfidenceLevel.INSUFFICIENT,
                }.get(gap.get("confidence", "none"), ConfidenceLevel.INSUFFICIENT),
                evidence=[{"source": d.get("supported_by", "analytics"), "detail": d["detail"]} for d in drivers[:4]],
                limitations=gap.get("limitations", []),
            ),
        }
    )

    # 6 Advice outcomes
    sections.append(
        {
            "id": "advice_outcomes",
            "title": "Advice-to-outcome",
            "summary": ao.get("summary", {}).get("claim", "No advice"),
            "items": ao.get("items", [])[:5],
            "counts": ao.get("counts"),
            "evidence": ao.get("summary"),
        }
    )

    # 7 Drift
    open_alerts = [a for a in drift.get("alerts", []) if a.get("status") in {"open", "confirmed", None}]
    sections.append(
        {
            "id": "drift_signals",
            "title": "Hidden drift signals",
            "summary": f"{len(open_alerts)} open drift alert(s)",
            "alerts": open_alerts,
            "evidence": envelope(
                "Multi-signal drift rules",
                confidence=ConfidenceLevel.VERIFIED if open_alerts else ConfidenceLevel.LIMITED,
                evidence=[{"source": "drift_detector", "detail": a["title"]} for a in open_alerts[:4]],
                limitations=["Missing data alerts are informational, not distress."],
            ),
        }
    )

    # 8 Commitments
    overdue = [a for a in snap.get("advice_history", []) if a.get("follow_up_status") == "overdue"]
    sections.append(
        {
            "id": "commitments",
            "title": "Outstanding commitments",
            "summary": f"{len(overdue)} overdue follow-up(s)",
            "items": overdue[:5],
            "evidence": envelope(
                "Advice follow-ups",
                confidence=ConfidenceLevel.VERIFIED if snap.get("advice_history") else ConfidenceLevel.INSUFFICIENT,
                severity="high" if overdue else "info",
                evidence=[{"source": "synthetic_advice.csv", "record_ids": [a["advice_id"] for a in overdue]}],
            ),
        }
    )

    # 9 Data quality
    missing = snap.get("missing_data_warnings") or []
    sections.append(
        {
            "id": "data_quality",
            "title": "Data quality",
            "summary": "; ".join(missing) if missing else "No material data-quality warnings",
            "warnings": missing,
            "evidence": envelope(
                "Freshness and completeness",
                confidence=ConfidenceLevel.LIMITED if missing else ConfidenceLevel.VERIFIED,
                severity="low" if missing else "info",
                missing_data=missing,
                evidence=[
                    {
                        "source": "synthetic_investors.csv",
                        "detail": f"freshness_days={snap['data_timestamps'].get('data_freshness_days')}",
                        "freshness_days": int(snap["data_timestamps"].get("data_freshness_days") or 0)
                        if str(snap["data_timestamps"].get("data_freshness_days")).isdigit()
                        else None,
                    }
                ],
                next_steps=["Refresh stale feeds before investment conclusions."] if missing else [],
            ),
        }
    )

    # 10 Recommended actions
    actions = []
    if pri["priority"] in {"Critical", "High"}:
        actions.append("Schedule review meeting with prepared brief")
    for a in open_alerts[:2]:
        actions.append(f"Review drift: {a['title']}")
    if overdue:
        actions.append("Close or reschedule overdue advice follow-ups")
    if not actions:
        actions.append("Maintain monitoring cadence")

    sections.append(
        {
            "id": "recommended_actions",
            "title": "Recommended review actions",
            "summary": "; ".join(actions),
            "actions": actions,
            "evidence": envelope(
                "Actions derived from priority + drift + commitments",
                confidence=ConfidenceLevel.LIMITED,
                evidence=[{"source": "attention_engine", "detail": pri["priority_reason"]}],
                limitations=["Suggestions for advisor review — not automated trades."],
                next_steps=actions,
            ),
        }
    )

    return {
        "investor_id": investor_id,
        "display_name": inv["display_name"],
        "priority": pri,
        "parts": sections,
        "part_ids": PARTS,
        "is_demo": True,
        "disclaimer": snap.get("disclaimer"),
    }
