"""Goal Agent — expected path deviation."""
from __future__ import annotations

from analytics.portfolio import DataStore, investor_snapshot
from domain.evidence import ConfidenceLevel, envelope, insufficient
from agents.schemas import AgentFinding


def run(store: DataStore, investor_id: str) -> AgentFinding:
    snap = investor_snapshot(store, investor_id)
    if snap.get("error"):
        return AgentFinding(
            agent="Goal",
            claim="Insufficient goal data",
            supported=False,
            rejected_reason=snap["error"],
            evidence=insufficient("Goal agent", [snap["error"]]),
        )
    gp = snap["goal_progress"]
    claim = (
        f"{gp['goal_name']}: {gp['deviation_pct_vs_expected']:+.1f}% vs expected path "
        f"({gp['years_remaining']:.1f}y remaining)"
    )
    return AgentFinding(
        agent="Goal",
        claim=claim,
        metrics=gp,
        evidence=envelope(
            claim,
            confidence=ConfidenceLevel.VERIFIED,
            severity="high" if gp["deviation_pct_vs_expected"] <= -8 else "info",
            evidence=[{"source": "synthetic_goals.csv", "detail": gp["methodology"]}],
        ),
        supported=True,
    )
