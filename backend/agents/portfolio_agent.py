"""Portfolio Agent — allocation & TWR from structured data only."""
from __future__ import annotations

from typing import Any

from analytics.portfolio import DataStore, investor_snapshot
from domain.evidence import ConfidenceLevel, envelope, insufficient
from agents.schemas import AgentFinding


def run(store: DataStore, investor_id: str) -> AgentFinding:
    snap = investor_snapshot(store, investor_id)
    if snap.get("error"):
        return AgentFinding(
            agent="Portfolio",
            claim="Insufficient portfolio data",
            supported=False,
            rejected_reason=snap["error"],
            evidence=insufficient("Portfolio agent", [snap["error"]]),
        )
    perf = snap["performance"]
    alloc = snap["allocation"]
    claim = (
        f"Portfolio value INR {snap['portfolio_value']:,.0f}; "
        f"TWR {perf.get('twr_window_pct')}% vs bench {perf.get('benchmark_twr_pct')}%"
    )
    return AgentFinding(
        agent="Portfolio",
        claim=claim,
        metrics={
            "portfolio_value": snap["portfolio_value"],
            "allocation": alloc,
            "twr": perf.get("twr_window_pct"),
            "benchmark_twr": perf.get("benchmark_twr_pct"),
            "active": perf.get("active_return_pct"),
        },
        evidence=envelope(
            claim,
            confidence=ConfidenceLevel.VERIFIED if perf.get("twr_window_pct") is not None else ConfidenceLevel.INSUFFICIENT,
            evidence=[{"source": "synthetic_holdings.csv+returns", "record_ids": [investor_id]}],
            limitations=[perf.get("methodology", "")],
        ),
        supported=perf.get("twr_window_pct") is not None,
        rejected_reason=None if perf.get("twr_window_pct") is not None else "Missing returns",
    )
