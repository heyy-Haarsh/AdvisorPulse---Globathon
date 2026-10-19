"""
Advice-to-Outcome Intelligence (Feature 2).

Structured advice history vs measurable outcomes. Deterministic calcs only.
Immutable/versioned advice snapshots. Returns "Insufficient data" when missing.
"""
from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from analytics.portfolio import DataStore, TODAY, allocation, goal_progress, twr_from_period_returns
from domain.evidence import ConfidenceLevel, envelope, insufficient
from domain.persistence import load_advice_versions, version_advice


def _parse_date(v: Any) -> date | None:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    try:
        return date.fromisoformat(str(v)[:10])
    except Exception:
        return None


def ensure_versions(store: DataStore, investor_id: str) -> None:
    """Seed immutable versions from CSV for advice rows not yet versioned."""
    existing = load_advice_versions()
    advice = store.advice[store.advice["investor_id"] == investor_id]
    for _, row in advice.iterrows():
        aid = str(row["advice_id"])
        if aid not in existing:
            version_advice(
                aid,
                {
                    "investor_id": investor_id,
                    "advice_date": str(row.get("advice_date")),
                    "recommendation": str(row.get("recommendation")),
                    "intended_outcome": str(row.get("intended_outcome")),
                    "follow_up_status": str(row.get("follow_up_status")),
                    "source": "synthetic_csv",
                },
            )


def evaluate_advice_item(
    store: DataStore,
    investor_id: str,
    advice_row: dict[str, Any],
) -> dict[str, Any]:
    """Deterministic outcome evaluation for one advice record."""
    aid = str(advice_row["advice_id"])
    rec = str(advice_row.get("recommendation") or "").lower()
    advice_date = _parse_date(advice_row.get("advice_date"))
    intended = str(advice_row.get("intended_outcome") or "")

    holdings = store.holdings[store.holdings["investor_id"] == investor_id]
    returns = store.returns[store.returns["investor_id"] == investor_id]
    goals = store.goals[store.goals["investor_id"] == investor_id]
    cashflows = store.cashflows[store.cashflows["investor_id"] == investor_id]

    metrics: dict[str, Any] = {}
    outcome_status = "Insufficient data"
    confidence = ConfidenceLevel.INSUFFICIENT
    evidence: list[dict[str, Any]] = []
    missing: list[str] = []

    if advice_date is None:
        missing.append("advice_date")

    # Allocation-related advice
    if "mid-cap" in rec or "rebalanc" in rec or "debt sleeve" in rec or "allocation" in rec:
        if holdings.empty:
            missing.append("holdings")
        else:
            alloc = {a["asset_class"]: a["weight_pct"] for a in allocation(holdings)}
            mid = alloc.get("Equity - Mid Cap", 0)
            debt = alloc.get("Debt - Duration", 0)
            metrics["mid_cap_weight_pct"] = mid
            metrics["debt_weight_pct"] = debt
            policy_mid, policy_debt = 15.0, 25.0
            mid_ok = abs(mid - policy_mid) <= 5
            debt_ok = abs(debt - policy_debt) <= 5
            if mid_ok and debt_ok:
                outcome_status = "Aligned with intended allocation"
            elif mid > policy_mid + 5:
                outcome_status = "Not yet aligned — mid-cap still overweight"
            else:
                outcome_status = "Partially aligned"
            confidence = ConfidenceLevel.VERIFIED if mid_ok or debt_ok else ConfidenceLevel.LIMITED
            evidence.append(
                {
                    "source": "synthetic_holdings.csv",
                    "record_ids": holdings["holding_id"].astype(str).tolist()[:5],
                    "as_of": str(holdings["as_of_date"].max()),
                    "detail": f"Mid-cap {mid:.1f}% (policy {policy_mid}%), Debt {debt:.1f}% (policy {policy_debt}%)",
                }
            )

    # SIP increase advice
    elif "sip" in rec:
        if goals.empty:
            missing.append("goals")
        else:
            g = goals.iloc[0]
            sip = float(g["required_monthly_sip"])
            metrics["required_monthly_sip"] = sip
            # Check contributions after advice date
            if advice_date and not cashflows.empty:
                after = cashflows[
                    (cashflows["flow_type"] == "contribution")
                    & (cashflows["date"].astype(str) >= advice_date.isoformat())
                ]
                if after.empty:
                    missing.append("post-advice contributions")
                    outcome_status = "Insufficient data"
                else:
                    avg = float(after["amount"].astype(float).mean())
                    metrics["avg_contribution_after"] = avg
                    if avg >= sip * 0.9:
                        outcome_status = "Funding cadence near advised SIP"
                        confidence = ConfidenceLevel.LIMITED
                    else:
                        outcome_status = "Contributions below advised SIP level"
                        confidence = ConfidenceLevel.LIMITED
                    evidence.append(
                        {
                            "source": "synthetic_cashflows.csv",
                            "record_ids": after["cashflow_id"].astype(str).tolist()[:5],
                            "detail": f"Avg contribution after advice: {avg:,.0f}",
                        }
                    )
            else:
                missing.append("cashflows_after_advice")
                outcome_status = "Insufficient data"

    # Withdrawal advice
    elif "withdrawal" in rec:
        if cashflows.empty:
            missing.append("cashflows")
        else:
            wd = cashflows[cashflows["flow_type"] == "withdrawal"]
            if wd.empty:
                outcome_status = "No withdrawal recorded"
                confidence = ConfidenceLevel.LIMITED
            else:
                total = float(wd["amount"].astype(float).sum())
                metrics["withdrawal_total"] = total
                status = str(advice_row.get("follow_up_status"))
                outcome_status = "Withdrawal executed" if status == "done" else "Withdrawal on file"
                confidence = ConfidenceLevel.VERIFIED
                evidence.append(
                    {
                        "source": "synthetic_cashflows.csv",
                        "record_ids": wd["cashflow_id"].astype(str).tolist(),
                        "detail": f"Net withdrawals {total:,.0f}",
                    }
                )
            # Separate TWR so we don't confuse cash flow with returns
            if not returns.empty:
                window = returns.sort_values("period").tail(6)
                twr = twr_from_period_returns(window["portfolio_return_pct"] / 100.0)
                metrics["twr_post_window_pct"] = round(twr * 100, 3)
                evidence.append(
                    {
                        "source": "synthetic_returns.csv",
                        "detail": f"TWR (chain-linked) {twr*100:.2f}% — separate from withdrawal cash effect",
                    }
                )

    # Goal path / generic
    else:
        if goals.empty:
            missing.append("goals")
            outcome_status = "Insufficient data"
        else:
            gp = goal_progress(goals.iloc[0].to_dict())
            metrics["deviation_pct_vs_expected"] = gp["deviation_pct_vs_expected"]
            if gp["deviation_pct_vs_expected"] >= -5:
                outcome_status = "Goal path near expected"
                confidence = ConfidenceLevel.LIMITED
            else:
                outcome_status = "Goal path still behind expected"
                confidence = ConfidenceLevel.LIMITED
            evidence.append(
                {
                    "source": "synthetic_goals.csv",
                    "record_ids": [str(goals.iloc[0]["goal_id"])],
                    "as_of": TODAY.isoformat(),
                    "detail": f"Deviation {gp['deviation_pct_vs_expected']:+.1f}% vs expected path",
                }
            )

    if missing and outcome_status == "Insufficient data":
        conf_env = insufficient(
            f"Outcome for advice {aid}",
            missing,
            next_steps=["Collect missing holdings/returns/cashflows before judging advice effectiveness."],
        )
    else:
        conf_env = envelope(
            f"Outcome for advice {aid}: {outcome_status}",
            confidence=confidence,
            severity="medium" if "Not yet" in outcome_status or "behind" in outcome_status else "info",
            evidence=evidence,
            missing_data=missing,
            limitations=[
                "Correlation ≠ causation: outcomes reflect many market and client factors.",
                "Deterministic comparison only — no fabricated performance.",
            ],
            next_steps=["Confirm whether advisor still wants this recommendation active."],
        )

    versions = load_advice_versions().get(aid, [])

    return {
        "advice_id": aid,
        "investor_id": investor_id,
        "advice_date": str(advice_row.get("advice_date")),
        "recommendation": advice_row.get("recommendation"),
        "intended_outcome": intended,
        "follow_up_status": advice_row.get("follow_up_status"),
        "follow_up_due": advice_row.get("follow_up_due"),
        "outcome_status": outcome_status,
        "metrics": metrics,
        "versions": versions,
        "immutable_note": "Advice text is versioned; edits create a new version, never overwrite.",
        "evidence": conf_env,
        "is_demo": True,
    }


def advice_outcome_report(store: DataStore, investor_id: str) -> dict[str, Any]:
    ensure_versions(store, investor_id)
    advice = store.advice[store.advice["investor_id"] == investor_id].sort_values(
        "advice_date", ascending=False
    )
    if advice.empty:
        return {
            "investor_id": investor_id,
            "items": [],
            "summary": insufficient(
                "Advice-to-outcome",
                ["advice history"],
                next_steps=["Record structured advice before outcome tracking."],
            ),
            "is_demo": True,
        }

    items = [evaluate_advice_item(store, investor_id, r.to_dict()) for _, r in advice.iterrows()]
    aligned = sum(1 for i in items if "Aligned" in i["outcome_status"] or "executed" in i["outcome_status"].lower() or "near" in i["outcome_status"].lower())
    insuff = sum(1 for i in items if i["outcome_status"] == "Insufficient data")

    return {
        "investor_id": investor_id,
        "items": items,
        "counts": {
            "total": len(items),
            "positive_or_aligned": aligned,
            "insufficient_data": insuff,
        },
        "summary": envelope(
            f"{aligned}/{len(items)} advice items show aligned or near-aligned outcomes; {insuff} insufficient",
            confidence=ConfidenceLevel.LIMITED if insuff else ConfidenceLevel.VERIFIED,
            evidence=[{"source": "advice_outcome_engine", "detail": f"{len(items)} evaluated"}],
            limitations=["Do not claim causal productivity gains from these counts alone."],
        ),
        "is_demo": True,
    }
