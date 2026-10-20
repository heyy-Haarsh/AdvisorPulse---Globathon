"""Broad-market compatibility + assumptions serialization."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from analytics.portfolio import DataStore, allocation  # noqa: E402
from services import market_shock as ms  # noqa: E402
from services.whatif import simulate  # noqa: E402


@pytest.fixture(scope="module")
def store():
    return DataStore.load()


def test_assumptions_catalog_serializable():
    cat = ms.assumptions_catalog()
    json.dumps(cat)
    assert cat["default_price_change_pct"] == -12.0
    assert cat["slider"]["max"] == 30.0


def test_default_12_run_deterministic(store):
    a = ms.run_book_simulation(store, equity_market_shock_pct=-12.0)
    b = ms.run_book_simulation(store, equity_market_shock_pct=-12.0)
    assert a["scenario"]["price_change_pct"] == -12.0
    assert a["summary"]["estimated_aggregate_impact"] == b["summary"]["estimated_aggregate_impact"]


def test_portfolio_impact_formula(store):
    iid = "DEMO-INV-001"
    r = ms.evaluate_client(store, iid, -12.0)
    assert r["estimated_impact_amount"] is not None
    holdings = store.holdings[store.holdings["investor_id"] == iid]
    alloc = allocation(holdings)
    v = sum(float(a["market_value"]) for a in alloc)
    r_i = 0.0
    for a in alloc:
        shock, _, _ = ms.resolve_class_shock(a["asset_class"], -12.0)
        r_i += (float(a["weight_pct"]) / 100.0) * float(shock)
    expected_stressed = v * (1.0 + r_i / 100.0)
    assert r["estimated_stressed_value"] == pytest.approx(expected_stressed, rel=1e-6)


def test_positive_broad_market(store):
    out = ms.run_book_simulation(store, equity_market_shock_pct=12.0)
    assert out.get("error") is None
    assert out["summary"]["estimated_aggregate_impact"] > 0


def test_sip_simulate_still_available_for_copilot(store):
    r = simulate(store, "DEMO-INV-001", sip_delta=10000)
    assert r.get("is_hypothetical") is True


def test_no_portfolio_mutation(store):
    before = store.holdings[store.holdings["investor_id"] == "DEMO-INV-001"]["market_value"].sum()
    ms.run_book_simulation(store, equity_market_shock_pct=-20.0)
    after = store.holdings[store.holdings["investor_id"] == "DEMO-INV-001"]["market_value"].sum()
    assert before == after


def test_mark_reviewed_audit_only(store):
    out = ms.mark_reviewed("DEMO-INV-001", scenario_equity_shock_pct=-12.0, note="demo")
    assert out["ok"] is True
