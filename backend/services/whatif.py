"""
What-If Simulator (Feature 8).

Explicit formulas. Baseline vs alternative. Assumptions disclosed. Hypothetical label.
Supports: SIP/contribution, allocation reweight (same AUM), hypothetical market shocks.
Security-level trades require holdings that are not exposed as tradeable lots — declined honestly.
"""
from __future__ import annotations

from typing import Any

from analytics.portfolio import DataStore, TODAY, allocation, goal_progress
from domain.evidence import ConfidenceLevel, envelope, insufficient
from services.drift import POLICY


def _fv_sip(seed: float, monthly: float, annual_pct: float, years: float) -> float:
    """Future value of seed + monthly SIP at constant annual rate (monthly compounding)."""
    months = max(0, int(round(years * 12)))
    r = annual_pct / 100.0 / 12.0
    value = seed
    for _ in range(months):
        value = value * (1 + r) + monthly
    return value


def simulate(
    store: DataStore,
    investor_id: str,
    *,
    sip_delta: float = 0.0,
    return_delta_pp: float = 0.0,
    years_override: float | None = None,
    lump_sum: float = 0.0,
) -> dict[str, Any]:
    goals = store.goals[store.goals["investor_id"] == investor_id]
    if goals.empty:
        return {
            "investor_id": investor_id,
            "error": "No goal",
            "evidence": insufficient("What-if simulation", ["goal"]),
            "is_hypothetical": True,
            "is_demo": True,
        }

    goal = goals.iloc[0].to_dict()
    gp = goal_progress(goal)
    current = float(gp["current_value"])
    years = float(years_override) if years_override is not None else float(gp["years_remaining"])
    base_sip = float(gp["required_monthly_sip"])
    base_ret = float(gp["expected_annual_return_pct"])

    alt_sip = base_sip + sip_delta
    alt_ret = base_ret + return_delta_pp
    seed = current + lump_sum

    baseline = _fv_sip(current, base_sip, base_ret, years)
    alternative = _fv_sip(seed, alt_sip, alt_ret, years)
    target = float(gp["target_amount"])

    assumptions = [
        f"Monthly compounding at constant annual rate (baseline {base_ret}%, alt {alt_ret}%).",
        f"SIP constant: baseline {base_sip:,.0f}/mo, alternative {alt_sip:,.0f}/mo.",
        f"Horizon {years:.2f} years from as-of {TODAY.isoformat()}.",
        "No taxes, fees, or sequence-of-returns risk modeled.",
        "HYPOTHETICAL — not a forecast or guarantee.",
    ]
    if lump_sum:
        assumptions.append(f"Immediate lump sum of {lump_sum:,.0f} added to alternative seed only.")

    formula = (
        "V_t = (...((seed*(1+r)+SIP)*(1+r)+SIP)...) for n months; "
        "r = annual_return/12; n = round(years*12)"
    )

    return {
        "investor_id": investor_id,
        "is_hypothetical": True,
        "label": "HYPOTHETICAL SCENARIO",
        "as_of": TODAY.isoformat(),
        "inputs": {
            "sip_delta": sip_delta,
            "return_delta_pp": return_delta_pp,
            "years": years,
            "lump_sum": lump_sum,
            "baseline_sip": base_sip,
            "baseline_return_pct": base_ret,
            "current_value": current,
            "target_amount": target,
        },
        "baseline": {
            "projected_value": round(baseline, 2),
            "gap_to_target": round(baseline - target, 2),
            "pct_of_target": round(100 * baseline / target, 2) if target else None,
        },
        "alternative": {
            "projected_value": round(alternative, 2),
            "gap_to_target": round(alternative - target, 2),
            "pct_of_target": round(100 * alternative / target, 2) if target else None,
        },
        "delta_vs_baseline": round(alternative - baseline, 2),
        "formula": formula,
        "assumptions": assumptions,
        "evidence": envelope(
            f"Alternative projects {alternative - baseline:+,.0f} vs baseline over {years:.1f}y",
            confidence=ConfidenceLevel.LIMITED,
            severity="info",
            evidence=[
                {
                    "source": "whatif_simulator",
                    "record_ids": [str(goal.get("goal_id"))],
                    "as_of": TODAY.isoformat(),
                    "detail": formula,
                }
            ],
            limitations=assumptions,
            next_steps=["Discuss affordability and risk tolerance before changing SIP."],
            is_hypothetical=True,
        ),
        "is_demo": True,
    }


def reproduce_hash_inputs(result: dict[str, Any]) -> tuple:
    """Stable tuple for reproducibility tests."""
    inp = result["inputs"]
    return (
        inp["sip_delta"],
        inp["return_delta_pp"],
        inp["years"],
        inp["lump_sum"],
        result["baseline"]["projected_value"],
        result["alternative"]["projected_value"],
    )


def _allocation_scenario(
    store: DataStore,
    investor_id: str,
    proposed_weights: dict[str, float],
) -> dict[str, Any]:
    holdings = store.holdings[store.holdings["investor_id"] == investor_id]
    if holdings.empty:
        return {
            "investor_id": investor_id,
            "scenario_type": "allocation_change",
            "error": "Holdings unavailable",
            "is_hypothetical": True,
            "evidence": insufficient("Allocation what-if", ["holdings"]),
            "is_demo": True,
        }

    current = allocation(holdings)
    total_value = float(sum(float(a["market_value"]) for a in current))
    baseline_rows = [
        {
            "asset_class": a["asset_class"],
            "weight_pct": round(float(a["weight_pct"]), 2),
            "market_value": round(float(a["market_value"]), 2),
            "policy_weight_pct": POLICY.get(a["asset_class"]),
        }
        for a in current
    ]

    # Normalize proposed to 100 if within 2pp; else reject
    raw_sum = sum(float(v) for v in proposed_weights.values())
    if raw_sum <= 0:
        return {
            "investor_id": investor_id,
            "scenario_type": "allocation_change",
            "error": "Proposed weights must be positive and sum near 100%",
            "is_hypothetical": True,
            "is_demo": True,
        }
    if abs(raw_sum - 100.0) > 2.0:
        return {
            "investor_id": investor_id,
            "scenario_type": "allocation_change",
            "error": f"Proposed weights sum to {raw_sum:.1f}% (must be within 2pp of 100)",
            "weight_sum": raw_sum,
            "is_hypothetical": True,
            "is_demo": True,
        }

    scale = 100.0 / raw_sum
    alt_rows = []
    for ac, w in proposed_weights.items():
        wt = float(w) * scale
        alt_rows.append(
            {
                "asset_class": ac,
                "weight_pct": round(wt, 2),
                "market_value": round(total_value * wt / 100.0, 2),
                "policy_weight_pct": POLICY.get(ac),
                "delta_pp_vs_current": round(
                    wt - next((r["weight_pct"] for r in baseline_rows if r["asset_class"] == ac), 0.0),
                    2,
                ),
            }
        )

    assumptions = [
        "HYPOTHETICAL reallocation of existing portfolio market value — no new capital assumed.",
        "Weights renormalized only when sum is within 2pp of 100%; original holdings unchanged.",
        "No transaction costs, taxes, or market impact modeled.",
        "Does not change security prices — only relative sleeve weights.",
    ]

    return {
        "investor_id": investor_id,
        "scenario_type": "allocation_change",
        "is_hypothetical": True,
        "label": "HYPOTHETICAL ALLOCATION SCENARIO",
        "as_of": TODAY.isoformat(),
        "portfolio_value": round(total_value, 2),
        "baseline_allocation": baseline_rows,
        "scenario_allocation": alt_rows,
        "funding": "reallocate_existing_holdings",
        "formula": "scenario_value_i = total_AUM * proposed_weight_i / 100",
        "assumptions": assumptions,
        "evidence": envelope(
            "Hypothetical reallocation of current AUM across asset classes",
            confidence=ConfidenceLevel.LIMITED,
            evidence=[{"source": "synthetic_holdings.csv", "record_ids": [investor_id]}],
            limitations=assumptions,
            is_hypothetical=True,
        ),
        "is_demo": True,
    }


def _market_shock_scenario(
    store: DataStore,
    investor_id: str,
    shocks: dict[str, float],
) -> dict[str, Any]:
    """shocks: asset_class -> percent return shock (e.g. -10 for -10%)."""
    holdings = store.holdings[store.holdings["investor_id"] == investor_id]
    if holdings.empty:
        return {
            "investor_id": investor_id,
            "scenario_type": "market_movement",
            "error": "Holdings unavailable",
            "is_hypothetical": True,
            "evidence": insufficient("Market shock what-if", ["holdings"]),
            "is_demo": True,
        }

    current = allocation(holdings)
    baseline_value = float(sum(float(a["market_value"]) for a in current))
    rows = []
    scenario_value = 0.0
    for a in current:
        ac = a["asset_class"]
        mv = float(a["market_value"])
        shock = float(shocks.get(ac, 0.0))
        new_mv = mv * (1.0 + shock / 100.0)
        scenario_value += new_mv
        rows.append(
            {
                "asset_class": ac,
                "shock_pct": shock,
                "baseline_value": round(mv, 2),
                "scenario_value": round(new_mv, 2),
                "gain_loss": round(new_mv - mv, 2),
            }
        )

    for ac, shock in shocks.items():
        if ac not in {r["asset_class"] for r in rows} and float(shock) != 0:
            # Shock on class with no holding — report zero exposure
            rows.append(
                {
                    "asset_class": ac,
                    "shock_pct": float(shock),
                    "baseline_value": 0.0,
                    "scenario_value": 0.0,
                    "gain_loss": 0.0,
                    "note": "No current holding in this class",
                }
            )

    # Resulting weights
    for r in rows:
        r["scenario_weight_pct"] = (
            round(100.0 * r["scenario_value"] / scenario_value, 2) if scenario_value else None
        )
        r["baseline_weight_pct"] = (
            round(100.0 * r["baseline_value"] / baseline_value, 2) if baseline_value else None
        )

    assumptions = [
        "HYPOTHETICAL instantaneous price/return shocks by asset class — not a forecast.",
        "No rebalancing, cash flows, taxes, or correlation structure modeled.",
        "Past returns do not guarantee future results.",
    ]

    return {
        "investor_id": investor_id,
        "scenario_type": "market_movement",
        "is_hypothetical": True,
        "label": "HYPOTHETICAL MARKET MOVEMENT",
        "as_of": TODAY.isoformat(),
        "baseline_portfolio_value": round(baseline_value, 2),
        "scenario_portfolio_value": round(scenario_value, 2),
        "delta_value": round(scenario_value - baseline_value, 2),
        "delta_pct": round(100.0 * (scenario_value - baseline_value) / baseline_value, 2)
        if baseline_value
        else None,
        "rows": rows,
        "shocks": shocks,
        "formula": "scenario_value_i = baseline_value_i * (1 + shock_pct_i/100)",
        "assumptions": assumptions,
        "evidence": envelope(
            "Hypothetical asset-class market shocks on current holdings",
            confidence=ConfidenceLevel.LIMITED,
            evidence=[{"source": "synthetic_holdings.csv", "record_ids": [investor_id]}],
            limitations=assumptions,
            is_hypothetical=True,
        ),
        "is_demo": True,
    }


def simulate_scenario(
    store: DataStore,
    investor_id: str,
    *,
    scenario_type: str = "sip_contribution",
    sip_delta: float = 0.0,
    return_delta_pp: float = 0.0,
    years_override: float | None = None,
    lump_sum: float = 0.0,
    proposed_weights: dict[str, float] | None = None,
    market_shocks: dict[str, float] | None = None,
) -> dict[str, Any]:
    """
    scenario_type:
      sip_contribution | allocation_change | market_movement | security_holding_change
    """
    st = (scenario_type or "sip_contribution").strip().lower()

    if st in {"sip", "sip_contribution", "contribution"}:
        result = simulate(
            store,
            investor_id,
            sip_delta=sip_delta,
            return_delta_pp=return_delta_pp,
            years_override=years_override,
            lump_sum=lump_sum,
        )
        result["scenario_type"] = "sip_contribution"
        return result

    if st in {"allocation", "allocation_change"}:
        return _allocation_scenario(store, investor_id, proposed_weights or {})

    if st in {"market", "market_movement", "market_shock"}:
        return _market_shock_scenario(store, investor_id, market_shocks or {})

    if st in {"security", "security_holding_change", "stock"}:
        return {
            "investor_id": investor_id,
            "scenario_type": "security_holding_change",
            "supported": False,
            "error": (
                "Security-level lots/prices are not exposed as tradeable instruments in this DEMO. "
                "Use allocation_change or market_movement at asset-class level instead."
            ),
            "is_hypothetical": True,
            "evidence": insufficient(
                "Security-level what-if",
                ["security_lots", "security_prices"],
                limitations=["Holdings are aggregated by asset class in the DEMO feed."],
            ),
            "is_demo": True,
        }

    return {
        "investor_id": investor_id,
        "error": f"Unknown scenario_type: {scenario_type}",
        "is_hypothetical": True,
        "is_demo": True,
    }
