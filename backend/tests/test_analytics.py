from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from analytics.portfolio import (  # noqa: E402
    DataStore,
    modified_dietz,
    twr_from_period_returns,
    investor_snapshot,
)
from prioritization.engine import score_investor, rank_book, overview_kpis  # noqa: E402
from ingestion.transactions import load_transactions, cashflow_signals  # noqa: E402
from summaries.generator import generate  # noqa: E402
import pandas as pd  # noqa: E402
from datetime import date  # noqa: E402


@pytest.fixture(scope="module")
def store():
    s = DataStore.load()
    assert len(s.investors) >= 200
    return s


def test_twr_chain():
    s = pd.Series([0.01, -0.02, 0.015])
    twr = twr_from_period_returns(s)
    expected = (1.01 * 0.98 * 1.015) - 1
    assert abs(twr - expected) < 1e-9


def test_modified_dietz_no_flow():
    r = modified_dietz(100, 110, [], date(2026, 1, 1), date(2026, 2, 1))
    assert abs(r - 0.10) < 1e-9


def test_priya_is_critical(store):
    pri = score_investor(store, "DEMO-INV-001")
    assert pri["priority"] in {"Critical", "High"}
    assert pri["goal_status"]["deviation_pct_vs_expected"] < -5


def test_arjun_not_critical(store):
    pri = score_investor(store, "DEMO-INV-002")
    assert pri["priority"] in {"Monitor", "On Track", "High"}
    # Should not be Critical due to suppression
    assert pri["priority"] != "Critical"
    assert any(f["name"] == "suppress_reason" for f in pri["factors"])


def test_snapshot_has_evidence(store):
    snap = investor_snapshot(store, "DEMO-INV-001")
    assert snap["is_demo"] is True
    assert "gap_explanation" in snap
    assert snap["gap_explanation"]["confidence"] in {"low", "medium", "high", "none"}
    summary = generate(snap, score_investor(store, "DEMO-INV-001"))
    assert "7200" in summary["summary_text"].replace(",", "") or "7,200" in summary["summary_text"]
    assert summary["llm_used"] is False


def test_overview_computed(store):
    ranked = rank_book(store)
    kpis = overview_kpis(ranked)
    assert kpis["total_clients"] == len(store.investors)
    assert sum(kpis["priority_distribution"].values()) == kpis["total_clients"]
    assert kpis["clients_requiring_review"] == (
        kpis["priority_distribution"].get("Critical", 0) + kpis["priority_distribution"].get("High", 0)
    )


def test_transaction_ingestion():
    path = Path(__file__).resolve().parents[2] / "data" / "sample_transactions.csv"
    df, report = load_transactions(path)
    assert report.rows_read > 0
    assert report.invalid_dates >= 1 or report.invalid_amounts >= 1
    signals = cashflow_signals(df)
    assert signals["available"] is True
    assert "limitations" in signals
