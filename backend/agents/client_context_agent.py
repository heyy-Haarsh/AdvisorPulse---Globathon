"""ClientContext Agent — priority, freshness, commitments."""
from __future__ import annotations

from analytics.portfolio import DataStore
from domain.evidence import ConfidenceLevel, envelope
from prioritization.engine import score_investor
from agents.schemas import AgentFinding


def run(store: DataStore, investor_id: str) -> AgentFinding:
    pri = score_investor(store, investor_id)
    claim = f"Priority {pri['priority']} (score {pri['score']}): {pri['priority_reason']}"
    return AgentFinding(
        agent="ClientContext",
        claim=claim,
        metrics={
            "priority": pri["priority"],
            "score": pri["score"],
            "data_quality_issue": pri.get("data_quality_issue"),
            "factors": pri.get("factors"),
        },
        evidence=envelope(
            claim,
            confidence=ConfidenceLevel.VERIFIED,
            severity=pri["priority"].lower() if pri["priority"] in {"Critical", "High"} else "info",
            evidence=[{"source": "prioritization.engine", "detail": f["detail"]} for f in pri.get("factors", [])[:4]],
        ),
        supported=True,
    )
