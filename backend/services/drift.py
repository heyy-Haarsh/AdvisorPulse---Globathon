"""
Hidden Financial Drift Detector (Feature 5).

Deterministic multi-signal rules. Suppress duplicates. Confirm/dismiss/resolve.
Never treat missing data as distress.
"""
from __future__ import annotations

from typing import Any

from analytics.portfolio import DataStore, TODAY, allocation, goal_progress, investor_snapshot
from domain.evidence import ConfidenceLevel, envelope, insufficient
from domain.persistence import load_drift_state, save_drift_state


POLICY = {
    "Equity - Large Cap": 35,
    "Equity - Mid Cap": 15,
    "Debt - Duration": 25,
    "Hybrid / Balanced": 15,
    "Cash / Liquid": 10,
}


def _alert_id(investor_id: str, rule: str) -> str:
    return f"{investor_id}::{rule}"


def detect_drift(store: DataStore, investor_id: str) -> dict[str, Any]:
    snap = investor_snapshot(store, investor_id)
    if snap.get("error"):
        return {
            "investor_id": investor_id,
            "alerts": [],
            "error": snap["error"],
            "is_demo": True,
        }

    inv = snap["investor"]
    freshness = inv.get("data_freshness_days")
    try:
        freshness_i = int(freshness)
    except Exception:
        freshness_i = None

    alerts: list[dict[str, Any]] = []
    state = load_drift_state()

    # Missing / stale data → informational only, NEVER distress
    if freshness_i is None or freshness_i >= 45 or freshness_i == 999:
        aid = _alert_id(investor_id, "stale_or_missing_valuation")
        prev = state.get(aid, {})
        if prev.get("status") not in {"dismissed", "resolved"}:
            alerts.append(
                {
                    "alert_id": aid,
                    "rule": "stale_or_missing_valuation",
                    "title": "Data freshness issue",
                    "severity": "low",
                    "is_distress": False,
                    "status": prev.get("status", "open"),
                    "evidence": envelope(
                        "Valuation freshness is stale or missing — not financial distress",
                        confidence=ConfidenceLevel.VERIFIED,
                        severity="low",
                        evidence=[
                            {
                                "source": "synthetic_investors.csv",
                                "record_ids": [investor_id],
                                "as_of": TODAY.isoformat(),
                                "detail": f"data_freshness_days={freshness}",
                                "freshness_days": freshness_i,
                            }
                        ],
                        next_steps=["Refresh feed before drawing investment conclusions."],
                    ),
                }
            )

    # Allocation drift vs policy
    holdings = store.holdings[store.holdings["investor_id"] == investor_id]
    if holdings.empty:
        # missing holdings — insufficient, not distress
        aid = _alert_id(investor_id, "missing_holdings")
        prev = state.get(aid, {})
        if prev.get("status") not in {"dismissed", "resolved"}:
            alerts.append(
                {
                    "alert_id": aid,
                    "rule": "missing_holdings",
                    "title": "Holdings unavailable",
                    "severity": "low",
                    "is_distress": False,
                    "status": prev.get("status", "open"),
                    "evidence": insufficient(
                        "Cannot assess allocation drift",
                        ["holdings"],
                        next_steps=["Load holdings before drift review."],
                    ),
                }
            )
    else:
        alloc = {a["asset_class"]: a["weight_pct"] for a in allocation(holdings)}
        for ac, target in POLICY.items():
            actual = alloc.get(ac, 0.0)
            drift_pp = actual - target
            if abs(drift_pp) < 5:
                continue
            rule = f"allocation_drift::{ac}"
            aid = _alert_id(investor_id, rule)
            prev = state.get(aid, {})
            if prev.get("status") in {"dismissed", "resolved"}:
                continue
            # Suppress duplicate of same rule already open with same bucket
            severity = "high" if abs(drift_pp) >= 10 else "medium"
            alerts.append(
                {
                    "alert_id": aid,
                    "rule": rule,
                    "title": f"Allocation drift — {ac}",
                    "severity": severity,
                    "is_distress": abs(drift_pp) >= 10,
                    "drift_pp": round(drift_pp, 2),
                    "status": prev.get("status", "open"),
                    "evidence": envelope(
                        f"{ac} at {actual:.1f}% vs policy {target:.1f}% (Δ {drift_pp:+.1f} pp)",
                        confidence=ConfidenceLevel.VERIFIED,
                        severity=severity,
                        evidence=[
                            {
                                "source": "synthetic_holdings.csv",
                                "record_ids": holdings["holding_id"].astype(str).tolist()[:5],
                                "as_of": str(holdings["as_of_date"].max()),
                                "detail": f"actual={actual:.1f} policy={target}",
                            }
                        ],
                        next_steps=["Confirm whether rebalancing discussion is warranted."],
                    ),
                }
            )

    # Goal path drift
    goals = store.goals[store.goals["investor_id"] == investor_id]
    if not goals.empty:
        gp = goal_progress(goals.iloc[0].to_dict())
        dev = gp["deviation_pct_vs_expected"]
        if dev <= -8:
            aid = _alert_id(investor_id, "goal_path_drift")
            prev = state.get(aid, {})
            if prev.get("status") not in {"dismissed", "resolved"}:
                alerts.append(
                    {
                        "alert_id": aid,
                        "rule": "goal_path_drift",
                        "title": "Goal path behind expected",
                        "severity": "critical" if dev <= -18 else "high",
                        "is_distress": True,
                        "deviation_pct": dev,
                        "status": prev.get("status", "open"),
                        "evidence": envelope(
                            f"Behind expected path by {dev:.1f}%",
                            confidence=ConfidenceLevel.VERIFIED,
                            severity="critical" if dev <= -18 else "high",
                            evidence=[
                                {
                                    "source": "synthetic_goals.csv",
                                    "record_ids": [str(goals.iloc[0]["goal_id"])],
                                    "as_of": TODAY.isoformat(),
                                    "detail": (
                                        f"current={gp['current_value']:,.0f} "
                                        f"expected={gp['expected_path_value']:,.0f}"
                                    ),
                                }
                            ],
                            next_steps=["Review SIP, allocation, and goal assumptions with client."],
                        ),
                    }
                )

    # SIP contribution shortfall (cashflow vs required)
    if not goals.empty and not store.cashflows.empty:
        gp = goal_progress(goals.iloc[0].to_dict())
        sip = gp["required_monthly_sip"]
        cf = store.cashflows[store.cashflows["investor_id"] == investor_id]
        contrib = cf[cf["flow_type"] == "contribution"]
        if not contrib.empty:
            recent = contrib.tail(3)
            avg = float(recent["amount"].astype(float).mean())
            if avg < sip * 0.75:
                aid = _alert_id(investor_id, "sip_shortfall")
                prev = state.get(aid, {})
                if prev.get("status") not in {"dismissed", "resolved"}:
                    alerts.append(
                        {
                            "alert_id": aid,
                            "rule": "sip_shortfall",
                            "title": "Contribution cadence below plan",
                            "severity": "medium",
                            "is_distress": False,
                            "status": prev.get("status", "open"),
                            "evidence": envelope(
                                f"Recent avg contribution {avg:,.0f} vs planned SIP {sip:,.0f}",
                                confidence=ConfidenceLevel.LIMITED,
                                severity="medium",
                                evidence=[
                                    {
                                        "source": "synthetic_cashflows.csv",
                                        "record_ids": recent["cashflow_id"].astype(str).tolist(),
                                        "detail": "Last 3 contributions vs required_monthly_sip",
                                    }
                                ],
                                limitations=["Short window; confirm banking feed completeness."],
                                next_steps=["Verify SIP mandate and client cash-flow capacity."],
                            ),
                        }
                    )

    # Deduplicate by rule family (keep highest severity)
    seen: dict[str, dict[str, Any]] = {}
    sev_rank = {"critical": 3, "high": 2, "medium": 1, "low": 0, "info": 0}
    for a in alerts:
        key = a["rule"].split("::")[0] if a["rule"].startswith("allocation_drift") else a["rule"]
        # allow multiple allocation drifts but suppress exact alert_id dupes
        if a["alert_id"] in seen:
            continue
        # For same non-allocation rule, keep one
        if not a["rule"].startswith("allocation_drift"):
            if key in {x["rule"].split("::")[0] if x["rule"].startswith("allocation_drift") else x["rule"] for x in seen.values()}:
                existing = next(
                    (v for v in seen.values() if (v["rule"].split("::")[0] if v["rule"].startswith("allocation_drift") else v["rule"]) == key),
                    None,
                )
                if existing and sev_rank.get(a["severity"], 0) <= sev_rank.get(existing["severity"], 0):
                    continue
        seen[a["alert_id"]] = a

    # Allocation vs policy comparison (additive — for Client Workspace)
    holdings = store.holdings[store.holdings["investor_id"] == investor_id]
    alloc_rows = allocation(holdings) if not holdings.empty else []
    actual_map = {a["asset_class"]: float(a["weight_pct"]) for a in alloc_rows}
    value_map = {a["asset_class"]: float(a["market_value"]) for a in alloc_rows}
    weight_sum = round(sum(actual_map.values()), 2)
    comparison = []
    all_classes = sorted(set(POLICY.keys()) | set(actual_map.keys()))
    for ac in all_classes:
        current = actual_map.get(ac)
        target = POLICY.get(ac)
        comparison.append(
            {
                "asset_class": ac,
                "current_weight_pct": None if current is None else round(current, 2),
                "policy_weight_pct": target,
                "delta_pp": None
                if current is None or target is None
                else round(current - target, 2),
                "market_value": value_map.get(ac),
                "in_policy": ac in POLICY,
            }
        )

    return {
        "investor_id": investor_id,
        "alerts": list(seen.values()),
        "suppressed_note": "Dismissed/resolved alerts omitted. Missing data never scored as distress.",
        "policy_weights": dict(POLICY),
        "allocation_vs_policy": {
            "rows": comparison,
            "weight_sum_pct": weight_sum,
            "weight_sum_ok": abs(weight_sum - 100.0) <= 0.6 if alloc_rows else False,
            "note": (
                "Weights are not silently normalized. "
                "Totals away from 100% indicate unclassified/other or data gaps."
                if alloc_rows
                else "Holdings unavailable — cannot compare to policy."
            ),
        },
        "is_demo": True,
    }


def update_drift_status(alert_id: str, status: str, note: str = "") -> dict[str, Any]:
    if status not in {"open", "confirmed", "dismissed", "resolved"}:
        raise ValueError("status must be open|confirmed|dismissed|resolved")
    return save_drift_state(alert_id, {"status": status, "note": note})
