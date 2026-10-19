"""AdviceOutcome Agent — wraps deterministic advice-outcome service."""
from __future__ import annotations

from analytics.portfolio import DataStore
from services.advice_outcome import advice_outcome_report
from agents.schemas import AgentFinding


def run(store: DataStore, investor_id: str) -> AgentFinding:
    report = advice_outcome_report(store, investor_id)
    counts = report.get("counts") or {}
    claim = report.get("summary", {}).get("claim") or "No advice outcomes"
    return AgentFinding(
        agent="AdviceOutcome",
        claim=claim,
        metrics=counts,
        evidence=report.get("summary") or {},
        supported=counts.get("total", 0) > 0,
        rejected_reason=None if counts.get("total", 0) > 0 else "No advice history",
    )
