"""Regression tests for Blind Spot Radar, Alert Quality Lab, Next Action, Txn DQ, QuantStats/verify."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agents.verification_agent import reject_fabricated_claim, verify  # noqa: E402
from agents.schemas import AgentFinding  # noqa: E402
from analytics.portfolio import DataStore  # noqa: E402
from analytics.quantstats_bridge import performance_crosscheck  # noqa: E402
from domain.evidence import ConfidenceLevel, envelope  # noqa: E402
from eval.alert_quality import evaluate  # noqa: E402
from ingestion.transactions import load_transactions  # noqa: E402
from prioritization.engine import score_investor  # noqa: E402
from services.blind_spot import BLIND_SPOT_HERO, build_radar  # noqa: E402
from services.review_action import build_pack, decide_pack  # noqa: E402
from services.txn_quality import validate_path  # noqa: E402

DATA = ROOT.parent / "data"


@pytest.fixture(scope="module")
def store():
    return DataStore.load()


def test_blind_spot_hero_less_observed(store):
    radar = build_radar(store, segment="less_observed")
    assert radar["hero"] is not None
    assert radar["hero"]["investor_id"] == BLIND_SPOT_HERO
    assert radar["hero"]["priority"] in {"Critical", "High"}
    assert radar["hero"]["segment"] == "less_observed"
    ids = [c["investor_id"] for c in radar["clients"][:5]]
    assert BLIND_SPOT_HERO in ids
    pri = score_investor(store, BLIND_SPOT_HERO)
    assert pri["score"] >= 76


def test_alert_quality_pulse_beats_baseline_on_material(store):
    result = evaluate(store)
    assert result["n_material"] >= 2
    assert result["pulse"]["recall_at_20"] >= result["baseline"]["recall_at_20"]
    # Seeded material cases should be in Pulse top-20
    for iid, rank in result["pulse"]["material_ranks"].items():
        assert rank > 0
        assert rank <= 20
    # Arjun false-alarm should not dominate Pulse top-20
    arjun_rank = result["pulse"]["false_alarm_ranks"].get("DEMO-INV-002", -1)
    assert arjun_rank == -1 or arjun_rank > 20
    assert "pulse_top_20" in result and len(result["pulse_top_20"]) == 20


def test_next_review_action_pack_and_decision(store):
    pack = build_pack(store, "DEMO-INV-001")
    assert pack["suggested_action"]["key"] in {
        "rebalance_review",
        "clarify_goal_or_withdrawal",
        "request_missing_data",
        "monitor_follow_up",
    }
    assert pack["client_message_status"] == "draft_requires_approval"
    assert len(pack["questions"]) >= 3
    decided = decide_pack(store, "DEMO-INV-001", decision="accept", note="pytest accept")
    assert decided["decision"] == "accept"
    assert decided.get("commitment")
    assert decided["client_message_status"] == "draft_requires_approval"

    arjun = build_pack(store, "DEMO-INV-002")
    assert arjun["suggested_action"]["key"] == "clarify_goal_or_withdrawal"


def test_dirty_txn_pipeline():
    path = DATA / "sample_transactions_dirty.csv"
    assert path.exists()
    result = validate_path(path)
    s = result["summary"]
    assert s["rows_read"] >= 8
    assert s["duplicates_flagged"] >= 1
    assert s["currency_normalized"] >= 1
    assert "not linked" in " ".join(s["limitations"]).lower() or "DEMO-INV" in s["identity_note"]
    # Layer-1 IDs — no silent DEMO-INV join in fixture user_ids
    df, _ = load_transactions(path)
    if not df.empty and "user_id" in df.columns:
        assert not any(str(u).startswith("DEMO-INV") for u in df["user_id"].astype(str))


def test_quantstats_crosscheck_demo_returns(store):
    cc = performance_crosscheck(store, "DEMO-INV-001")
    assert cc["available"] is True
    assert "native" in cc
    assert cc["native"]["max_drawdown"] == cc["native"]["max_drawdown"]  # not NaN silently zeroed
    method = (cc.get("methodology") or "").lower()
    assert "portfolio_return" in method or "demo monthly" in method
    assert "not transaction" in method


def test_whatif_allocation_and_market_scenarios(store):
    from services.whatif import simulate_scenario

    sip = simulate_scenario(store, "DEMO-INV-001", scenario_type="sip_contribution", sip_delta=5000)
    assert sip.get("is_hypothetical") is True
    assert "baseline" in sip

    alloc = simulate_scenario(
        store,
        "DEMO-INV-001",
        scenario_type="allocation_change",
        proposed_weights={
            "Equity - Large Cap": 40,
            "Equity - Mid Cap": 10,
            "Debt - Duration": 25,
            "Hybrid / Balanced": 15,
            "Cash / Liquid": 10,
        },
    )
    assert alloc.get("scenario_type") == "allocation_change"
    assert alloc.get("portfolio_value")
    assert abs(sum(r["weight_pct"] for r in alloc["scenario_allocation"]) - 100) < 1.5

    mkt = simulate_scenario(
        store,
        "DEMO-INV-001",
        scenario_type="market_movement",
        market_shocks={"Equity - Mid Cap": -10},
    )
    assert mkt["delta_value"] is not None

    stock = simulate_scenario(store, "DEMO-INV-001", scenario_type="security_holding_change")
    assert stock.get("supported") is False


def test_drift_includes_allocation_vs_policy(store):
    from services.drift import detect_drift

    d = detect_drift(store, "DEMO-INV-001")
    assert "allocation_vs_policy" in d
    assert "policy_weights" in d
    assert d["allocation_vs_policy"]["rows"]


def test_verification_rejects_fabricated_numeric_claim():
    rejected = reject_fabricated_claim("Client returned 94% precision without sources")
    assert rejected.supported is False
    assert rejected.rejected_reason

    ok = verify(
        AgentFinding(
            agent="test",
            claim="Goal deviation is -12.5%",
            metrics={"deviation_pct": -12.5},
            evidence=envelope(
                "Goal deviation is -12.5%",
                confidence=ConfidenceLevel.VERIFIED,
                evidence=[{"source": "goals", "record_ids": ["DEMO-INV-001"]}],
            ),
        )
    )
    assert ok.supported is True
