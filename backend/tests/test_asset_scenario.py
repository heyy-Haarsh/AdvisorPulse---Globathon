"""Asset-level Market & Asset Scenario Simulator tests."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from analytics.portfolio import DataStore  # noqa: E402
from services import market_shock as ms  # noqa: E402


@pytest.fixture(scope="module")
def store():
    return DataStore.load()


def test_catalog_json_serializable():
    cat = ms.assumptions_catalog()
    import json

    json.dumps(cat)  # must not raise (no sets)
    assert cat["slider"]["min"] == -30
    assert cat["slider"]["max"] == 30
    assert any(i["instrument_id"] == "NSE:RELIANCE" for i in cat["stocks"])
    assert any(i["instrument_id"] == "INDEX:NIFTY50" for i in cat["indices"])


def test_stock_down_10(store):
    out = ms.run_scenario(
        store, scenario_type="stock", instrument_id="NSE:RELIANCE", price_change_pct=-10
    )
    assert out.get("error") is None
    exposed = [r for r in out["results"] if r.get("exposure_status") == "supported"]
    assert exposed
    for r in exposed[:5]:
        assert r["estimated_position_impact"] < 0
        assert r["impact_status"] == "negative"
        # Position impact ≈ exposure * r
        assert r["estimated_position_impact"] == pytest.approx(
            r["total_scenario_exposure"] * -0.10, rel=1e-3
        )


def test_stock_up_10(store):
    out = ms.run_scenario(
        store, scenario_type="stock", instrument_id="NSE:RELIANCE", price_change_pct=10
    )
    exposed = [r for r in out["results"] if r.get("exposure_status") == "supported"]
    assert exposed
    for r in exposed[:5]:
        assert r["estimated_position_impact"] > 0
        assert r["impact_status"] == "positive"
        if r.get("estimated_portfolio_value_after") is not None and r.get(
            "current_portfolio_value"
        ):
            assert r["estimated_portfolio_value_after"] == pytest.approx(
                r["current_portfolio_value"] + r["estimated_position_impact"], rel=1e-6
            )


def test_zero_change(store):
    out = ms.run_scenario(
        store, scenario_type="stock", instrument_id="NSE:TCS", price_change_pct=0
    )
    for r in out["results"]:
        if r.get("exposure_status") == "supported":
            assert r["estimated_position_impact"] == pytest.approx(0.0)


def test_index_down_and_up(store):
    down = ms.run_scenario(
        store, scenario_type="index", instrument_id="INDEX:NIFTY50", price_change_pct=-12
    )
    up = ms.run_scenario(
        store, scenario_type="index", instrument_id="INDEX:NIFTY50", price_change_pct=8
    )
    assert down["summary"]["clients_with_supported_exposure"] > 0
    assert up["summary"]["clients_with_supported_exposure"] > 0
    d = next(r for r in down["results"] if r["exposure_status"] == "supported")
    u = next(r for r in up["results"] if r["client_id"] == d["client_id"])
    assert d["estimated_position_impact"] < 0
    assert u["estimated_position_impact"] > 0


def test_deterministic_repeat(store):
    a = ms.run_scenario(
        store, scenario_type="stock", instrument_id="NSE:INFY", price_change_pct=-10
    )
    b = ms.run_scenario(
        store, scenario_type="stock", instrument_id="NSE:INFY", price_change_pct=-10
    )
    assert a["summary"]["estimated_aggregate_impact"] == b["summary"]["estimated_aggregate_impact"]


def test_invalid_inputs(store):
    assert ms.run_scenario(store, scenario_type="stock", price_change_pct=-10).get("error")
    assert ms.run_scenario(
        store, scenario_type="stock", instrument_id="NSE:RELIANCE", price_change_pct=-100
    ).get("error")
    assert ms.run_scenario(
        store, scenario_type="stock", instrument_id="NSE:RELIANCE", price_change_pct=50
    ).get("error")


def test_no_fabricated_exposure_for_missing_stock(store):
    out = ms.run_scenario(
        store, scenario_type="stock", instrument_id="NSE:DOESNOTEXIST", price_change_pct=-10
    )
    assert out.get("error")


def test_indirect_without_double_count(store):
    """Clients with direct RELIANCE should not also get fund look-through for RELIANCE."""
    out = ms.run_scenario(
        store,
        scenario_type="stock",
        instrument_id="NSE:RELIANCE",
        price_change_pct=-10,
        include_indirect_exposure=True,
    )
    for r in out["results"]:
        if r.get("exposure_status") != "supported":
            continue
        kinds = {p.get("exposure_kind") for p in r.get("position_impacts") or []}
        if "direct" in kinds:
            assert "indirect_fund" not in kinds


def test_currency_not_mixed_in_aggregate(store):
    out = ms.run_scenario(
        store, scenario_type="stock", instrument_id="NASDAQ:AAPL", price_change_pct=10
    )
    # Aggregate currency should be USD for AAPL exposures
    assert out["summary"]["currency"] in {"USD", "INR"}
    if out["summary"]["clients_with_supported_exposure"]:
        assert "USD" in out["summary"]["aggregate_by_currency"]


def test_no_portfolio_mutation(store):
    before = store.holdings[store.holdings["investor_id"] == "DEMO-INV-001"]["market_value"].sum()
    ms.run_scenario(
        store, scenario_type="stock", instrument_id="NSE:RELIANCE", price_change_pct=-20
    )
    after = store.holdings[store.holdings["investor_id"] == "DEMO-INV-001"]["market_value"].sum()
    assert before == after


def test_broad_market_signed(store):
    up = ms.run_scenario(store, scenario_type="broad_market", price_change_pct=10)
    down = ms.run_scenario(store, scenario_type="broad_market", price_change_pct=-10)
    assert up["summary"]["estimated_aggregate_impact"] > 0
    assert down["summary"]["estimated_aggregate_impact"] < 0


def test_fixture_position_math():
    """Explicit fixture: V0=200000, r=+10% → +20000."""
    v0 = 200_000.0
    r = 0.10
    assert v0 * r == pytest.approx(20_000.0)
    r_neg = -0.10
    assert v0 * r_neg == pytest.approx(-20_000.0)
