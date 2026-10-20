"""
Market & Asset Scenario Simulator.

Supports:
  - Individual stock (direct + documented indirect look-through)
  - Market index (trackers / approximate sensitivities)
  - Broad equity-market scenario (asset-class sensitivities)

Signed price movements (−30% … +30%). Deterministic. Hypothetical only.
Does not mutate portfolio records or Attention Engine rankings.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from analytics.portfolio import DataStore, TODAY, allocation
from domain.evidence import ConfidenceLevel, envelope, insufficient
from domain.persistence import audit, load_commitments, load_settings
from prioritization.engine import score_investor

ASSUMPTIONS_VERSION = "demo-v1"
ROOT = Path(__file__).resolve().parents[2]
CATALOG_PATH = ROOT / "data" / "demo" / "instrument_catalog.json"
POSITIONS_PATH = ROOT / "data" / "demo" / "security_positions.csv"

# Broad-market asset-class sensitivities to equity shock (signed)
DEFAULT_SENSITIVITY: dict[str, dict[str, Any]] = {
    "Equity - Large Cap": {"mode": "equity_beta", "beta": 1.0, "note": "Full sensitivity to equity-market shock"},
    "Equity - Mid Cap": {"mode": "equity_beta", "beta": 1.15, "note": "Illustrative higher beta"},
    "Hybrid / Balanced": {"mode": "equity_beta", "beta": 0.55, "note": "Partial equity participation"},
    "Debt - Duration": {"mode": "absolute", "shock_pct": 0.5, "note": "Mild absolute assumption under equity stress"},
    "Cash / Liquid": {"mode": "absolute", "shock_pct": 0.0, "note": "Zero price change"},
}

PRESETS = [
    {"id": "severe_down", "label": "−20% — Severe decline", "price_change_pct": -20.0},
    {"id": "mod_down", "label": "−10% — Moderate decline", "price_change_pct": -10.0},
    {"id": "small_down", "label": "−5% — Small decline", "price_change_pct": -5.0},
    {"id": "flat", "label": "0% — No change", "price_change_pct": 0.0},
    {"id": "small_up", "label": "+5% — Small increase", "price_change_pct": 5.0},
    {"id": "mod_up", "label": "+10% — Moderate increase", "price_change_pct": 10.0},
    {"id": "strong_up", "label": "+20% — Strong increase", "price_change_pct": 20.0},
    {"id": "default_demo", "label": "−12% — Default demo", "price_change_pct": -12.0},
]

RULES = {
    "material_impact_pct": 1.0,  # |portfolio impact pct| >= this for review consideration
    "material_position_impact": 100_000.0,
    "high_exposure_pct_of_portfolio": 15.0,
    "conservative_profiles": ["Conservative"],
    "review_priorities": ["high", "moderate", "monitor", "insufficient_data", "no_exposure"],
}

_catalog_cache: dict[str, Any] | None = None
_positions_cache: pd.DataFrame | None = None


def _load_catalog() -> dict[str, Any]:
    global _catalog_cache
    if _catalog_cache is None:
        _catalog_cache = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    return _catalog_cache


def _load_positions() -> pd.DataFrame:
    global _positions_cache
    if _positions_cache is None:
        if POSITIONS_PATH.exists():
            _positions_cache = pd.read_csv(POSITIONS_PATH)
        else:
            _positions_cache = pd.DataFrame()
    return _positions_cache


def _accessible(investor_id: str) -> bool:
    allowed = load_settings().get("accessible_clients")
    if allowed is None:
        return True
    return investor_id in set(allowed)


def list_instruments(kind: str | None = None) -> list[dict[str, Any]]:
    cat = _load_catalog()
    out = []
    for inst in cat.get("instruments") or []:
        if kind and inst.get("instrument_type") != kind:
            continue
        out.append({**inst, "is_demo": True})
    return out


def assumptions_catalog() -> dict[str, Any]:
    cat = _load_catalog()
    stocks = [i for i in cat["instruments"] if i["instrument_type"] == "stock"]
    indices = [i for i in cat["instruments"] if i["instrument_type"] == "index"]
    return {
        "assumptions_version": ASSUMPTIONS_VERSION,
        "is_demo": True,
        "is_hypothetical": True,
        "default_price_change_pct": -12.0,
        "slider": {"min": -30.0, "max": 30.0, "step": 1.0},
        "presets": PRESETS,
        "scenario_types": [
            {"id": "stock", "label": "Individual Stock"},
            {"id": "index", "label": "Market Index"},
            {"id": "broad_market", "label": "Broad-Market Scenario"},
        ],
        "instruments": cat["instruments"],
        "stocks": stocks,
        "indices": indices,
        "asset_class_assumptions": [
            {
                "asset_class": ac,
                "mode": cfg["mode"],
                "beta": cfg.get("beta"),
                "absolute_shock_pct": cfg.get("shock_pct"),
                "note": cfg["note"],
            }
            for ac, cfg in DEFAULT_SENSITIVITY.items()
        ],
        "review_rules": {**RULES, "conservative_profiles": list(RULES["conservative_profiles"])},
        "formula": {
            "stock": "Delta_V = V_0 * r; V_after = V_portfolio + Delta_V (supported exposures only)",
            "index": "Delta_V = exposure_value * r * sensitivity",
            "broad_market": "R_i = sum w_k * r_k; V_stressed = V * (1 + R_i)",
        },
        "disclaimer": (
            "Synthetic DEMO instruments and reference prices — not a live market feed. "
            "Hypothetical scenarios do not predict client behavior or recommend trades."
        ),
        # Backward-compatible keys for older UI
        "default_equity_market_shock_pct": -12.0,
        "demo_highlights": {},
    }


def resolve_class_shock(
    asset_class: str,
    equity_market_shock_pct: float,
    sensitivity: dict[str, dict[str, Any]] | None = None,
) -> tuple[float | None, str, list[str]]:
    sens = sensitivity or DEFAULT_SENSITIVITY
    cfg = sens.get(asset_class)
    if not cfg:
        return None, "unsupported_asset_class", [f"No scenario mapping for {asset_class}"]
    if cfg["mode"] == "equity_beta":
        return float(equity_market_shock_pct) * float(cfg["beta"]), f"equity_beta={cfg['beta']}", []
    if cfg["mode"] == "absolute":
        # Absolute assumptions keep their sign independent of equity direction for demo debt/cash
        # For signed broad market, scale absolute debt assumption with sign of shock when non-zero
        base = float(cfg["shock_pct"])
        if equity_market_shock_pct == 0:
            return 0.0, "absolute_assumption", []
        # Keep documented absolute for debt/cash (cash 0, debt small positive) — not flipped
        return base if asset_class != "Cash / Liquid" else 0.0, "absolute_assumption", []
    return None, "unknown_mode", [f"Unknown mode for {asset_class}"]


def _instrument_by_id(instrument_id: str) -> dict[str, Any] | None:
    for inst in _load_catalog().get("instruments") or []:
        if inst["instrument_id"] == instrument_id:
            return inst
    return None


def _portfolio_value(store: DataStore, investor_id: str) -> tuple[float | None, str]:
    holdings = store.holdings[store.holdings["investor_id"] == investor_id]
    if holdings.empty:
        return None, "INR"
    alloc = allocation(holdings)
    currencies = set(str(c) for c in holdings["currency"].unique())
    # Portfolio totals in DEMO are INR sleeves; USD security overlays are not added to AUM
    total = float(sum(float(a["market_value"]) for a in alloc))
    return total, "INR" if "INR" in currencies or not currencies else next(iter(currencies))


def _direct_stock_positions(instrument_id: str) -> pd.DataFrame:
    pos = _load_positions()
    if pos.empty:
        return pos
    return pos[pos["instrument_id"] == instrument_id].copy()


def _indirect_stock_exposures(
    store: DataStore,
    instrument_id: str,
    direct_investor_ids: set[str],
) -> list[dict[str, Any]]:
    """Fund look-through — skip investors already counted via direct holding of same stock."""
    cat = _load_catalog()
    out: list[dict[str, Any]] = []
    for mapping in cat.get("indirect_fund_constituents") or []:
        if mapping.get("constituent_id") != instrument_id:
            continue
        fund_id = mapping["fund_instrument_id"]
        weight = float(mapping["weight_pct"]) / 100.0
        held = store.holdings[store.holdings["instrument_id"] == fund_id]
        for _, row in held.iterrows():
            iid = str(row["investor_id"])
            if iid in direct_investor_ids:
                # Prevent double-count when client already has direct stock line
                continue
            if not _accessible(iid):
                continue
            fund_mv = float(row["market_value"])
            exposure = fund_mv * weight
            out.append(
                {
                    "investor_id": iid,
                    "account_id": f"{iid}-FUND",
                    "position_id": f"IND-{iid}-{instrument_id}-{fund_id}",
                    "holding_instrument_id": fund_id,
                    "instrument_id": instrument_id,
                    "exposure_kind": "indirect_fund",
                    "quantity": None,
                    "reference_price": None,
                    "market_value": round(exposure, 2),
                    "currency": str(row.get("currency") or "INR"),
                    "sensitivity": 1.0,
                    "note": mapping.get("note"),
                    "fund_market_value": round(fund_mv, 2),
                    "constituent_weight_pct": mapping["weight_pct"],
                }
            )
    return out


def _index_exposures(store: DataStore, index_id: str) -> list[dict[str, Any]]:
    cat = _load_catalog()
    trackers = [t for t in cat.get("index_trackers") or [] if t.get("tracks_index") == index_id]
    # Also include security positions that track this index
    pos = _load_positions()
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    for t in trackers:
        hold_id = t["holding_instrument_id"]
        sens = float(t.get("sensitivity") or 1.0)
        kind = t.get("exposure_kind") or "approximate_benchmark"
        # Sleeve holdings
        held = store.holdings[store.holdings["instrument_id"] == hold_id]
        for _, row in held.iterrows():
            iid = str(row["investor_id"])
            key = (iid, hold_id)
            if key in seen:
                continue
            seen.add(key)
            if not _accessible(iid):
                continue
            out.append(
                {
                    "investor_id": iid,
                    "account_id": f"{iid}-IDX",
                    "position_id": f"IDX-{iid}-{hold_id}",
                    "holding_instrument_id": hold_id,
                    "instrument_id": index_id,
                    "exposure_kind": kind,
                    "quantity": float(row["quantity"]) if pd.notna(row.get("quantity")) else None,
                    "reference_price": None,
                    "market_value": round(float(row["market_value"]), 2),
                    "currency": str(row.get("currency") or "INR"),
                    "sensitivity": sens,
                    "note": t.get("note"),
                }
            )
        # Security overlay positions with same holding_instrument_id
        if not pos.empty:
            sec = pos[pos["holding_instrument_id"] == hold_id]
            for _, row in sec.iterrows():
                iid = str(row["investor_id"])
                key = (iid, f"sec:{hold_id}")
                if key in seen or (iid, hold_id) in seen:
                    # Already counted via sleeve — skip overlay to avoid double-count
                    continue
                if not _accessible(iid):
                    continue
                seen.add(key)
                out.append(
                    {
                        "investor_id": iid,
                        "account_id": str(row.get("account_id") or f"{iid}-EQ"),
                        "position_id": str(row["position_id"]),
                        "holding_instrument_id": hold_id,
                        "instrument_id": index_id,
                        "exposure_kind": kind,
                        "quantity": float(row["quantity"]) if pd.notna(row.get("quantity")) else None,
                        "reference_price": float(row["reference_price"])
                        if pd.notna(row.get("reference_price"))
                        else None,
                        "market_value": round(float(row["market_value"]), 2),
                        "currency": str(row.get("currency") or "INR"),
                        "sensitivity": sens,
                        "note": t.get("note"),
                    }
                )
    return out


def _impact_status(delta: float | None) -> str:
    if delta is None:
        return "unavailable"
    if abs(delta) < 1e-9:
        return "neutral"
    return "positive" if delta > 0 else "negative"


def _review_for_signed(
    *,
    impact_pct: float | None,
    impact_amount: float | None,
    exposure_value: float,
    portfolio_value: float | None,
    price_change_pct: float,
    risk_profile: str,
) -> tuple[str, list[str]]:
    if impact_amount is None or impact_pct is None or portfolio_value is None:
        return "insufficient_data", ["Supported exposure or portfolio value unavailable"]
    if abs(exposure_value) < 1e-9 and abs(impact_amount) < 1e-9:
        return "no_exposure", ["No supported exposure to the selected instrument"]

    reasons: list[str] = []
    exp_pct = 100.0 * exposure_value / portfolio_value if portfolio_value else 0.0
    material = abs(impact_pct) >= RULES["material_impact_pct"] or abs(impact_amount) >= RULES[
        "material_position_impact"
    ]
    high_exp = exp_pct >= RULES["high_exposure_pct_of_portfolio"]
    conservative_hit = (
        risk_profile in RULES["conservative_profiles"]
        and price_change_pct < 0
        and high_exp
        and material
    )

    if material:
        direction = "decrease" if impact_amount < 0 else "increase"
        reasons.append(
            f"Material estimated portfolio-value {direction} "
            f"({impact_pct:+.2f}% / {impact_amount:+,.0f})"
        )
    if high_exp:
        reasons.append(f"Selected-scenario exposure is {exp_pct:.1f}% of known portfolio value")
    if conservative_hit:
        reasons.append(
            "Conservative documented risk profile with material negative scenario impact "
            "and high selected-instrument exposure"
        )

    if conservative_hit or (price_change_pct < 0 and material and high_exp):
        return "high", reasons
    if material or high_exp:
        return "moderate", reasons or ["Elevated selected-scenario exposure"]
    if abs(impact_pct) > 0.1:
        return "monitor", reasons or ["Modest estimated impact — monitor"]
    return "monitor", reasons or ["Limited estimated impact under this scenario"]


def run_scenario(
    store: DataStore,
    *,
    scenario_type: str = "broad_market",
    instrument_id: str | None = None,
    price_change_pct: float = -12.0,
    include_indirect_exposure: bool = True,
    assumptions_version: str = ASSUMPTIONS_VERSION,
    advisor_id: str = "DEMO-ADV-USER-01",
    scenario_name: str | None = None,
) -> dict[str, Any]:
    st = (scenario_type or "broad_market").strip().lower()
    if st in {"broad", "market", "equity_market"}:
        st = "broad_market"
    if st in {"stock", "equity", "individual_stock"}:
        st = "stock"
    if st in {"index", "market_index"}:
        st = "index"

    if assumptions_version != ASSUMPTIONS_VERSION:
        return {"error": f"Unsupported assumptions_version (supported: {ASSUMPTIONS_VERSION})"}

    if price_change_pct < -30 or price_change_pct > 30:
        return {"error": "price_change_pct must be between -30 and +30"}
    # Reject scenario prices that would go non-positive for stocks when ref price exists
    price_change_pct = float(round(price_change_pct))
    r = price_change_pct / 100.0
    if r <= -1.0:
        return {"error": "price_change_pct must be greater than -100% to keep scenario price positive"}

    ts = datetime.now(timezone.utc).isoformat()

    if st == "broad_market":
        return _run_broad_market(
            store,
            price_change_pct=price_change_pct,
            scenario_name=scenario_name,
            advisor_id=advisor_id,
            ts=ts,
        )
    if st == "stock":
        if not instrument_id:
            return {"error": "instrument_id is required for stock scenarios"}
        return _run_stock(
            store,
            instrument_id=instrument_id,
            price_change_pct=price_change_pct,
            include_indirect=include_indirect_exposure,
            scenario_name=scenario_name,
            advisor_id=advisor_id,
            ts=ts,
        )
    if st == "index":
        if not instrument_id:
            return {"error": "instrument_id is required for index scenarios"}
        return _run_index(
            store,
            index_id=instrument_id,
            price_change_pct=price_change_pct,
            scenario_name=scenario_name,
            advisor_id=advisor_id,
            ts=ts,
        )
    return {"error": f"Unknown scenario_type: {scenario_type}"}


def _run_stock(
    store: DataStore,
    *,
    instrument_id: str,
    price_change_pct: float,
    include_indirect: bool,
    scenario_name: str | None,
    advisor_id: str,
    ts: str,
) -> dict[str, Any]:
    inst = _instrument_by_id(instrument_id)
    if not inst or inst.get("instrument_type") != "stock":
        return {"error": f"Unknown or non-stock instrument: {instrument_id}"}

    ref_price = float(inst["reference_price"])
    scenario_price = ref_price * (1.0 + price_change_pct / 100.0)
    if scenario_price <= 0:
        return {"error": "Scenario price would be non-positive"}

    direct = _direct_stock_positions(instrument_id)
    direct_ids = set(direct["investor_id"].astype(str)) if not direct.empty else set()
    indirect_rows = (
        _indirect_stock_exposures(store, instrument_id, direct_ids) if include_indirect else []
    )

    # Build per-client exposure lists
    by_client: dict[str, list[dict[str, Any]]] = {}
    for _, row in direct.iterrows():
        iid = str(row["investor_id"])
        if not _accessible(iid):
            continue
        by_client.setdefault(iid, []).append(
            {
                "position_id": str(row["position_id"]),
                "account_id": str(row.get("account_id")),
                "exposure_kind": "direct",
                "quantity": float(row["quantity"]) if pd.notna(row.get("quantity")) else None,
                "reference_price": float(row["reference_price"])
                if pd.notna(row.get("reference_price"))
                else ref_price,
                "market_value": float(row["market_value"]),
                "currency": str(row["currency"]),
                "sensitivity": 1.0,
                "note": row.get("note"),
            }
        )
    for row in indirect_rows:
        by_client.setdefault(row["investor_id"], []).append(row)

    results = []
    for _, inv in store.investors.iterrows():
        iid = str(inv["investor_id"])
        if not _accessible(iid):
            continue
        positions = by_client.get(iid, [])
        results.append(
            _client_result_from_positions(
                store,
                iid,
                str(inv["display_name"]),
                str(inv.get("risk_profile") or "Unknown"),
                positions,
                price_change_pct=price_change_pct,
                instrument_id=instrument_id,
                ref_price=ref_price,
                scenario_price=scenario_price,
            )
        )

    # Incomplete demo edge
    if _accessible("DEMO-INV-MS-INC"):
        results.append(_incomplete_client_row("DEMO-INV-MS-INC", instrument_id))

    return _package_response(
        store,
        results=results,
        scenario_type="stock",
        instrument=inst,
        price_change_pct=price_change_pct,
        scenario_price=scenario_price,
        scenario_name=scenario_name
        or f"{inst['symbol']} {price_change_pct:+g}%",
        advisor_id=advisor_id,
        ts=ts,
        method="direct_and_indirect_stock_exposure",
    )


def _run_index(
    store: DataStore,
    *,
    index_id: str,
    price_change_pct: float,
    scenario_name: str | None,
    advisor_id: str,
    ts: str,
) -> dict[str, Any]:
    inst = _instrument_by_id(index_id)
    if not inst or inst.get("instrument_type") != "index":
        return {"error": f"Unknown or non-index instrument: {index_id}"}

    ref_price = float(inst["reference_price"])
    scenario_price = ref_price * (1.0 + price_change_pct / 100.0)
    exposures = _index_exposures(store, index_id)
    by_client: dict[str, list[dict[str, Any]]] = {}
    for e in exposures:
        by_client.setdefault(e["investor_id"], []).append(e)

    results = []
    for _, inv in store.investors.iterrows():
        iid = str(inv["investor_id"])
        if not _accessible(iid):
            continue
        results.append(
            _client_result_from_positions(
                store,
                iid,
                str(inv["display_name"]),
                str(inv.get("risk_profile") or "Unknown"),
                by_client.get(iid, []),
                price_change_pct=price_change_pct,
                instrument_id=index_id,
                ref_price=ref_price,
                scenario_price=scenario_price,
            )
        )
    if _accessible("DEMO-INV-MS-INC"):
        results.append(_incomplete_client_row("DEMO-INV-MS-INC", index_id))

    return _package_response(
        store,
        results=results,
        scenario_type="index",
        instrument=inst,
        price_change_pct=price_change_pct,
        scenario_price=scenario_price,
        scenario_name=scenario_name or f"{inst['symbol']} {price_change_pct:+g}%",
        advisor_id=advisor_id,
        ts=ts,
        method="index_tracker_and_sensitivity_mapping",
    )


def _client_result_from_positions(
    store: DataStore,
    investor_id: str,
    display_name: str,
    risk_profile: str,
    positions: list[dict[str, Any]],
    *,
    price_change_pct: float,
    instrument_id: str,
    ref_price: float,
    scenario_price: float,
) -> dict[str, Any]:
    portfolio_value, port_ccy = _portfolio_value(store, investor_id)
    r = price_change_pct / 100.0

    if not positions:
        return {
            "client_id": investor_id,
            "display_name": display_name,
            "instrument_id": instrument_id,
            "current_portfolio_value": round(portfolio_value, 2) if portfolio_value else None,
            "direct_exposure_value": 0.0,
            "indirect_exposure_value": 0.0,
            "total_scenario_exposure": 0.0,
            "estimated_position_impact": 0.0 if portfolio_value is not None else None,
            "estimated_portfolio_value_after": round(portfolio_value, 2) if portfolio_value else None,
            "estimated_portfolio_impact_pct": 0.0 if portfolio_value else None,
            "impact_status": "neutral" if portfolio_value is not None else "unavailable",
            "exposure_status": "no_supported_exposure"
            if portfolio_value is not None
            else "exposure_unknown",
            "position_impacts": [],
            "currency_breakdown": {},
            "risk_profile_context": {"stated_risk_profile": risk_profile},
            "review_priority": "no_exposure" if portfolio_value is not None else "insufficient_data",
            "review_reasons": [
                "No supported exposure found"
                if portfolio_value is not None
                else "Exposure unknown — portfolio valuation missing"
            ],
            "confidence": "Verified" if portfolio_value is not None else "Insufficient",
            "missing_inputs": [] if portfolio_value is not None else ["portfolio_valuation"],
            "suggested_actions": ["Monitor the scenario without taking immediate action."],
            "is_hypothetical": True,
            "is_demo": True,
        }

    # Group by currency — do not mix
    by_ccy: dict[str, list[dict[str, Any]]] = {}
    for p in positions:
        by_ccy.setdefault(str(p.get("currency") or "INR"), []).append(p)

    primary_ccy = "INR" if "INR" in by_ccy else next(iter(by_ccy))
    position_impacts = []
    direct_exp = 0.0
    indirect_exp = 0.0
    impact_primary = 0.0
    currency_breakdown: dict[str, dict[str, float]] = {}

    for ccy, plist in by_ccy.items():
        ccy_impact = 0.0
        ccy_exp = 0.0
        for p in plist:
            v0 = float(p["market_value"])
            sens = float(p.get("sensitivity") or 1.0)
            delta = v0 * r * sens
            kind = str(p.get("exposure_kind") or "direct")
            if ccy == primary_ccy:
                if kind == "direct":
                    direct_exp += v0
                else:
                    indirect_exp += v0
                impact_primary += delta
            ccy_impact += delta
            ccy_exp += v0
            position_impacts.append(
                {
                    "position_id": p.get("position_id"),
                    "account_id": p.get("account_id"),
                    "exposure_kind": kind,
                    "baseline_value": round(v0, 2),
                    "sensitivity": sens,
                    "assumed_return_pct": round(price_change_pct * sens, 4),
                    "estimated_impact": round(delta, 2),
                    "currency": ccy,
                    "quantity": p.get("quantity"),
                    "reference_price": p.get("reference_price") or ref_price,
                    "scenario_price": round(
                        (p.get("reference_price") or ref_price) * (1 + r), 4
                    )
                    if (p.get("reference_price") or ref_price)
                    else scenario_price,
                    "note": p.get("note"),
                }
            )
        currency_breakdown[ccy] = {
            "exposure": round(ccy_exp, 2),
            "estimated_impact": round(ccy_impact, 2),
        }

    total_exp = direct_exp + indirect_exp
    # Portfolio % only when primary currency matches portfolio currency (INR DEMO)
    impact_pct = None
    after = None
    if portfolio_value and port_ccy == primary_ccy:
        after = portfolio_value + impact_primary
        impact_pct = 100.0 * impact_primary / portfolio_value
    elif portfolio_value and primary_ccy != port_ccy:
        # Cannot mix — report position impact only
        after = None
        impact_pct = None

    review_priority, reasons = _review_for_signed(
        impact_pct=impact_pct if impact_pct is not None else (
            100.0 * impact_primary / total_exp if total_exp else None
        ),
        impact_amount=impact_primary,
        exposure_value=total_exp,
        portfolio_value=portfolio_value if port_ccy == primary_ccy else total_exp,
        price_change_pct=price_change_pct,
        risk_profile=risk_profile,
    )
    if impact_pct is None and port_ccy != primary_ccy:
        reasons = [
            f"Currency mismatch: exposure in {primary_ccy}, portfolio AUM in {port_ccy}. "
            "Impacts not converted — no fabricated FX.",
            *reasons,
        ]
        review_priority = "moderate" if abs(impact_primary) >= RULES["material_position_impact"] else "monitor"

    conf = "Verified"
    if any(p.get("exposure_kind") not in {"direct", "direct_index_tracker"} for p in positions):
        conf = "Limited"
    if impact_pct is None and portfolio_value:
        conf = "Limited"

    return {
        "client_id": investor_id,
        "display_name": display_name,
        "instrument_id": instrument_id,
        "current_portfolio_value": round(portfolio_value, 2) if portfolio_value else None,
        "direct_exposure_value": round(direct_exp, 2),
        "indirect_exposure_value": round(indirect_exp, 2),
        "total_scenario_exposure": round(total_exp, 2),
        "estimated_position_impact": round(impact_primary, 2),
        "estimated_portfolio_value_after": round(after, 2) if after is not None else None,
        "estimated_portfolio_impact_pct": round(impact_pct, 4) if impact_pct is not None else None,
        "impact_status": _impact_status(impact_primary),
        "exposure_status": "supported",
        "position_impacts": position_impacts,
        "currency_breakdown": currency_breakdown,
        "primary_impact_currency": primary_ccy,
        "risk_profile_context": {
            "stated_risk_profile": risk_profile,
            "exposure_pct_of_portfolio": round(100.0 * total_exp / portfolio_value, 2)
            if portfolio_value and port_ccy == primary_ccy
            else None,
        },
        "attention_signals": _attention_signals(store, investor_id),
        "review_priority": review_priority,
        "review_reasons": reasons,
        "confidence": conf,
        "missing_inputs": [],
        "suggested_actions": _suggestions(review_priority, price_change_pct),
        "evidence": envelope(
            f"{display_name}: {impact_primary:+,.0f} {primary_ccy} on {instrument_id}",
            confidence=ConfidenceLevel.VERIFIED if conf == "Verified" else ConfidenceLevel.LIMITED,
            evidence=[
                {
                    "source": "security_positions+instrument_catalog",
                    "record_ids": [investor_id, instrument_id],
                    "as_of": TODAY.isoformat(),
                }
            ],
            limitations=[
                "Hypothetical scenario — not a forecast.",
                "Indirect exposures use documented DEMO look-through weights only.",
            ],
            is_hypothetical=True,
        ),
        "is_hypothetical": True,
        "is_demo": True,
        # Compatibility aliases for prior UI
        "estimated_impact_amount": round(impact_primary, 2),
        "estimated_impact_pct": round(impact_pct, 4) if impact_pct is not None else None,
        "estimated_stressed_value": round(after, 2) if after is not None else None,
    }


def _incomplete_client_row(investor_id: str, instrument_id: str) -> dict[str, Any]:
    return {
        "client_id": investor_id,
        "display_name": "Demo Incomplete Allocation",
        "instrument_id": instrument_id,
        "current_portfolio_value": None,
        "direct_exposure_value": None,
        "indirect_exposure_value": None,
        "total_scenario_exposure": None,
        "estimated_position_impact": None,
        "estimated_portfolio_value_after": None,
        "estimated_portfolio_impact_pct": None,
        "impact_status": "unavailable",
        "exposure_status": "exposure_unknown",
        "position_impacts": [],
        "currency_breakdown": {},
        "risk_profile_context": {"stated_risk_profile": "Unknown"},
        "review_priority": "insufficient_data",
        "review_reasons": ["Incomplete instrument coverage — impact not fabricated"],
        "confidence": "Insufficient",
        "missing_inputs": ["holdings", "quantity", "reference_price"],
        "suggested_actions": ["Verify missing portfolio or instrument mapping data."],
        "evidence": insufficient("Asset scenario", ["holdings"]),
        "is_hypothetical": True,
        "is_demo": True,
        "estimated_impact_amount": None,
        "estimated_impact_pct": None,
        "estimated_stressed_value": None,
    }


def _suggestions(priority: str, price_change_pct: float) -> list[str]:
    out = []
    if priority in {"high", "moderate"}:
        if price_change_pct < 0:
            out.append("Prepare for a client discussion about potential volatility.")
            out.append("Review the client's current allocation against their documented risk profile.")
        else:
            out.append("Note potential concentration benefit; confirm suitability still holds.")
            out.append("Review whether gains change rebalancing or goal-funding plans.")
    if priority == "insufficient_data":
        out.append("Verify missing portfolio or instrument mapping data.")
    if not out:
        out.append("Monitor the scenario without taking immediate action.")
    return out[:4]


def _attention_signals(store: DataStore, investor_id: str) -> dict[str, Any]:
    try:
        pri = score_investor(store, investor_id)
    except Exception:
        return {"available": False}
    commits = [
        c
        for c in load_commitments()
        if str(c.get("investor_id")) == investor_id
        and str(c.get("status", "")).lower() in {"open", "overdue", "pending"}
    ]
    return {
        "available": True,
        "attention_priority": pri.get("priority"),
        "attention_score": pri.get("score"),
        "has_overdue_followup": bool(pri.get("has_overdue_followup")),
        "open_commitments": len(commits),
        "note": "Attention Engine priority is independent; not overwritten by this scenario.",
    }


def _package_response(
    store: DataStore,
    *,
    results: list[dict[str, Any]],
    scenario_type: str,
    instrument: dict[str, Any] | None,
    price_change_pct: float,
    scenario_price: float | None,
    scenario_name: str,
    advisor_id: str,
    ts: str,
    method: str,
) -> dict[str, Any]:
    rank = {
        "high": 0,
        "moderate": 1,
        "monitor": 2,
        "no_exposure": 3,
        "insufficient_data": 4,
    }
    results.sort(
        key=lambda r: (
            rank.get(str(r.get("review_priority")), 9),
            -abs(float(r.get("estimated_position_impact") or r.get("estimated_impact_amount") or 0)),
        )
    )

    with_exposure = [
        r
        for r in results
        if (r.get("total_scenario_exposure") or 0) not in (0, None)
        and r.get("exposure_status") == "supported"
    ]
    incomplete = [
        r
        for r in results
        if r.get("review_priority") == "insufficient_data"
        or r.get("exposure_status") == "exposure_unknown"
    ]
    for_review = [r for r in results if r.get("review_priority") in {"high", "moderate"}]

    # Aggregate by currency — never mix
    agg_by_ccy: dict[str, float] = {}
    for r in with_exposure:
        ccy = str(r.get("primary_impact_currency") or "INR")
        delta = float(r.get("estimated_position_impact") or 0)
        agg_by_ccy[ccy] = agg_by_ccy.get(ccy, 0.0) + delta

    primary_ccy = "INR" if "INR" in agg_by_ccy else (next(iter(agg_by_ccy)) if agg_by_ccy else "INR")
    aggregate_impact = agg_by_ccy.get(primary_ccy)
    if len(agg_by_ccy) > 1:
        aggregate_note = (
            f"Primary aggregate in {primary_ccy}. Other currencies kept separate: "
            + ", ".join(f"{k}={v:+,.2f}" for k, v in agg_by_ccy.items() if k != primary_ccy)
        )
    else:
        aggregate_note = (
            "Aggregate is the sum of supported position-level impacts in the primary currency "
            "(selected instrument / mapped exposures), not a full-book mark-to-market of every sleeve."
        )

    impact_buckets = _signed_buckets(with_exposure)
    priority_counts = {
        k: sum(1 for r in results if r.get("review_priority") == k)
        for k in RULES["review_priorities"]
    }

    audit(
        "asset_scenario_run",
        {
            "advisor_id": advisor_id,
            "scenario_type": scenario_type,
            "instrument_id": (instrument or {}).get("instrument_id"),
            "price_change_pct": price_change_pct,
            "clients_with_exposure": len(with_exposure),
        },
    )

    direction = (
        "neutral"
        if price_change_pct == 0
        else ("positive" if price_change_pct > 0 else "negative")
    )

    return {
        "scenario": {
            "name": scenario_name,
            "scenario_type": scenario_type,
            "instrument_id": (instrument or {}).get("instrument_id"),
            "instrument": instrument,
            "price_change_pct": price_change_pct,
            "scenario_direction": direction,
            "reference_price": (instrument or {}).get("reference_price"),
            "scenario_price": scenario_price,
            "price_source": (instrument or {}).get("price_source"),
            "price_timestamp": (instrument or {}).get("price_timestamp"),
            "assumptions_version": ASSUMPTIONS_VERSION,
            "is_hypothetical": True,
            "calculation_timestamp": ts,
            "as_of_portfolio": TODAY.isoformat(),
            "calculation_method": method,
            # Compat
            "equity_market_shock_pct": price_change_pct if scenario_type == "broad_market" else None,
        },
        "summary": {
            "clients_evaluated": len(results),
            "clients_with_supported_exposure": len(with_exposure),
            "clients_for_review": len(for_review),
            "incomplete_estimates": len(incomplete),
            "estimated_aggregate_impact": round(aggregate_impact, 2)
            if aggregate_impact is not None
            else None,
            "aggregate_impact_label": (
                "potential portfolio-value increase"
                if (aggregate_impact or 0) > 0
                else "potential portfolio-value decrease"
                if (aggregate_impact or 0) < 0
                else "no price-driven aggregate impact"
            ),
            "currency": primary_ccy,
            "aggregate_by_currency": {k: round(v, 2) for k, v in agg_by_ccy.items()},
            "coverage_note": aggregate_note,
            # Compat with prior UI
            "estimated_total_portfolio_impact": round(aggregate_impact, 2)
            if aggregate_impact is not None
            else None,
        },
        "results": results,
        "charts": {
            "impact_amount_buckets": impact_buckets,
            "review_priority_counts": priority_counts,
            "impact_pct_buckets": impact_buckets,
        },
        "assumptions": [
            f"Scenario type: {scenario_type}",
            f"Hypothetical price movement: {price_change_pct:+g}%",
            f"Reference price: {(instrument or {}).get('reference_price')} "
            f"({(instrument or {}).get('price_source')})",
            "Synthetic DEMO data — not live market quotes.",
            "Review priority is separate from Attention Engine severity.",
        ],
        "data_quality": {
            "complete_records": len(with_exposure),
            "partial_records": len(incomplete),
            "excluded_records": 0,
            "clients_without_exposure": sum(
                1 for r in results if r.get("exposure_status") == "no_supported_exposure"
            ),
            "warnings": [
                "Hypothetical results are not persisted into portfolio valuations.",
            ],
        },
        "is_demo": True,
        "is_hypothetical": True,
        "evidence": envelope(
            f"{scenario_type} scenario {price_change_pct:+g}% — {len(with_exposure)} exposed clients",
            confidence=ConfidenceLevel.LIMITED,
            evidence=[{"source": "market_shock.run_scenario", "as_of": ts}],
            limitations=["Not a market forecast; does not predict client behavior."],
            is_hypothetical=True,
        ),
    }


def _signed_buckets(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    edges = [
        (-1e18, -500_000),
        (-500_000, -100_000),
        (-100_000, -10_000),
        (-10_000, 0),
        (0, 10_000),
        (10_000, 100_000),
        (100_000, 500_000),
        (500_000, 1e18),
    ]
    labels = [
        "< −5L",
        "−5L to −1L",
        "−1L to −10k",
        "−10k to 0",
        "0 to +10k",
        "+10k to +1L",
        "+1L to +5L",
        "> +5L",
    ]
    out = []
    for (lo, hi), lab in zip(edges, labels):
        count = 0
        for r in results:
            v = r.get("estimated_position_impact")
            if v is None:
                continue
            v = float(v)
            if lo == -1e18:
                if v < hi:
                    count += 1
            elif hi == 1e18:
                if v >= lo:
                    count += 1
            else:
                if lo <= v < hi:
                    count += 1
        out.append({"bucket": lab, "lo": lo, "hi": hi, "count": count})
    return out


def _run_broad_market(
    store: DataStore,
    *,
    price_change_pct: float,
    scenario_name: str | None,
    advisor_id: str,
    ts: str,
) -> dict[str, Any]:
    """Asset-class weighted broad equity scenario (signed)."""
    results = []
    for _, inv in store.investors.iterrows():
        iid = str(inv["investor_id"])
        if not _accessible(iid):
            continue
        results.append(
            _evaluate_broad_client(
                store,
                iid,
                str(inv["display_name"]),
                str(inv.get("risk_profile") or "Unknown"),
                price_change_pct,
            )
        )
    if _accessible("DEMO-INV-MS-INC"):
        results.append(_incomplete_client_row("DEMO-INV-MS-INC", "BROAD_MARKET"))

    class_shocks = {
        ac: resolve_class_shock(ac, price_change_pct)[0] for ac in DEFAULT_SENSITIVITY
    }
    packaged = _package_response(
        store,
        results=results,
        scenario_type="broad_market",
        instrument={
            "instrument_id": "BROAD_EQUITY",
            "name": "Broad equity market",
            "symbol": "BROAD",
            "instrument_type": "broad_market",
            "currency": "INR",
            "reference_price": None,
            "price_source": "scenario_assumption",
            "price_timestamp": ts,
        },
        price_change_pct=price_change_pct,
        scenario_price=None,
        scenario_name=scenario_name or f"Broad equity {price_change_pct:+g}%",
        advisor_id=advisor_id,
        ts=ts,
        method="asset_class_weighted_shock",
    )
    packaged["scenario"]["resolved_class_shocks_pct"] = class_shocks
    packaged["assumptions"].extend(
        [f"{ac}: mapped return {class_shocks[ac]}%" for ac in DEFAULT_SENSITIVITY]
    )
    return packaged


def _evaluate_broad_client(
    store: DataStore,
    investor_id: str,
    display_name: str,
    risk_profile: str,
    price_change_pct: float,
) -> dict[str, Any]:
    holdings = store.holdings[store.holdings["investor_id"] == investor_id]
    if holdings.empty:
        return _incomplete_client_row(investor_id, "BROAD_MARKET") | {
            "display_name": display_name,
            "risk_profile_context": {"stated_risk_profile": risk_profile},
        }
    alloc_rows = allocation(holdings)
    current_value = float(sum(float(a["market_value"]) for a in alloc_rows))
    if current_value <= 0:
        return _incomplete_client_row(investor_id, "BROAD_MARKET") | {
            "display_name": display_name
        }

    exposure = []
    scenario_value = 0.0
    for a in alloc_rows:
        ac = str(a["asset_class"])
        mv = float(a["market_value"])
        shock, mode_note, miss = resolve_class_shock(ac, price_change_pct)
        if shock is None:
            return _incomplete_client_row(investor_id, "BROAD_MARKET") | {
                "display_name": display_name,
                "missing_inputs": miss,
            }
        new_mv = mv * (1.0 + shock / 100.0)
        scenario_value += new_mv
        exposure.append(
            {
                "asset_class": ac,
                "weight_pct": round(float(a["weight_pct"]), 2),
                "baseline_value": round(mv, 2),
                "assumed_return_pct": round(shock, 4),
                "scenario_value": round(new_mv, 2),
                "contribution_to_impact": round(new_mv - mv, 2),
                "assumption": mode_note,
                "supported": True,
            }
        )
    impact = scenario_value - current_value
    impact_pct = 100.0 * impact / current_value
    review_priority, reasons = _review_for_signed(
        impact_pct=impact_pct,
        impact_amount=impact,
        exposure_value=sum(
            float(e["baseline_value"])
            for e in exposure
            if str(e["asset_class"]).startswith("Equity")
        ),
        portfolio_value=current_value,
        price_change_pct=price_change_pct,
        risk_profile=risk_profile,
    )
    return {
        "client_id": investor_id,
        "display_name": display_name,
        "instrument_id": "BROAD_EQUITY",
        "current_portfolio_value": round(current_value, 2),
        "direct_exposure_value": round(current_value, 2),
        "indirect_exposure_value": 0.0,
        "total_scenario_exposure": round(current_value, 2),
        "estimated_position_impact": round(impact, 2),
        "estimated_portfolio_value_after": round(scenario_value, 2),
        "estimated_portfolio_impact_pct": round(impact_pct, 4),
        "impact_status": _impact_status(impact),
        "exposure_status": "supported",
        "exposure_breakdown": exposure,
        "position_impacts": [
            {
                "position_id": e["asset_class"],
                "exposure_kind": "asset_class",
                "baseline_value": e["baseline_value"],
                "estimated_impact": e["contribution_to_impact"],
                "assumed_return_pct": e["assumed_return_pct"],
                "currency": "INR",
            }
            for e in exposure
        ],
        "currency_breakdown": {"INR": {"exposure": round(current_value, 2), "estimated_impact": round(impact, 2)}},
        "primary_impact_currency": "INR",
        "risk_profile_context": {"stated_risk_profile": risk_profile},
        "attention_signals": _attention_signals(store, investor_id),
        "review_priority": review_priority,
        "review_reasons": reasons,
        "confidence": "Verified",
        "missing_inputs": [],
        "suggested_actions": _suggestions(review_priority, price_change_pct),
        "is_hypothetical": True,
        "is_demo": True,
        "estimated_impact_amount": round(impact, 2),
        "estimated_impact_pct": round(impact_pct, 4),
        "estimated_stressed_value": round(scenario_value, 2),
    }


# ---------- Backward-compatible wrappers for prior tests / API ----------


def run_book_simulation(
    store: DataStore,
    *,
    equity_market_shock_pct: float = -12.0,
    scenario_name: str | None = None,
    assumptions_version: str = ASSUMPTIONS_VERSION,
    preset_id: str | None = None,
    include_goal_impact: bool = True,
    advisor_id: str = "DEMO-ADV-USER-01",
) -> dict[str, Any]:
    """Legacy broad-market entrypoint (now allows signed shocks via run_scenario)."""
    # Map old negative-only presets
    return run_scenario(
        store,
        scenario_type="broad_market",
        instrument_id=None,
        price_change_pct=float(equity_market_shock_pct),
        include_indirect_exposure=True,
        assumptions_version=assumptions_version,
        advisor_id=advisor_id,
        scenario_name=scenario_name,
    )


def evaluate_client(
    store: DataStore,
    investor_id: str,
    equity_market_shock_pct: float,
    *,
    include_goal_impact: bool = True,
    sensitivity: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    inv = store.investors[store.investors["investor_id"] == investor_id]
    if inv.empty:
        return _incomplete_client_row(investor_id, "BROAD_MARKET")
    return _evaluate_broad_client(
        store,
        investor_id,
        str(inv.iloc[0]["display_name"]),
        str(inv.iloc[0].get("risk_profile") or "Unknown"),
        equity_market_shock_pct,
    )


def mark_reviewed(
    investor_id: str,
    *,
    scenario_equity_shock_pct: float,
    note: str = "",
    advisor_id: str = "DEMO-ADV-USER-01",
) -> dict[str, Any]:
    if not _accessible(investor_id):
        return {"denied": True, "message": "Access denied"}
    rec = {
        "investor_id": investor_id,
        "scenario_equity_shock_pct": scenario_equity_shock_pct,
        "note": note,
        "advisor_id": advisor_id,
        "marked_at": datetime.now(timezone.utc).isoformat(),
        "is_hypothetical": True,
    }
    audit("market_shock_reviewed", rec)
    return {"ok": True, "record": rec, "is_demo": True}
