"""
Multi-Agent Financial Analysis coordinator (Feature 6).

Runs modular agents, merges verified findings, rejects unsupported claims.
All numbers remain deterministic from analytics — no LLM invents metrics.
"""
from __future__ import annotations

from typing import Any

from analytics.portfolio import DataStore
from agents import (
    advice_outcome_agent,
    cashflow_agent,
    client_context_agent,
    goal_agent,
    portfolio_agent,
)
from agents.schemas import AgentBundle, AgentFinding
from agents.verification_agent import verify_bundle
from domain.evidence import ConfidenceLevel, envelope


def run_analysis(store: DataStore, investor_id: str) -> dict[str, Any]:
    findings: list[AgentFinding] = [
        portfolio_agent.run(store, investor_id),
        goal_agent.run(store, investor_id),
        cashflow_agent.run(store, investor_id),
        advice_outcome_agent.run(store, investor_id),
        client_context_agent.run(store, investor_id),
    ]
    verified, rejected = verify_bundle(findings)
    merged = " | ".join(f.claim for f in verified) or "No verified findings"
    bundle = AgentBundle(
        investor_id=investor_id,
        findings=findings,
        verified=verified,
        rejected=rejected,
        merged_summary=merged,
        is_demo=True,
    )
    payload = bundle.model_dump()
    payload["verification"] = {
        "verified_count": len(verified),
        "rejected_count": len(rejected),
        "note": "InsightVerification rejects unsupported or Insufficient claims.",
    }
    payload["evidence"] = envelope(
        merged[:240],
        confidence=ConfidenceLevel.VERIFIED if verified else ConfidenceLevel.INSUFFICIENT,
        evidence=[{"source": f.agent, "detail": f.claim} for f in verified],
        limitations=[f"Rejected: {r.agent} — {r.rejected_reason}" for r in rejected],
    )
    return payload
