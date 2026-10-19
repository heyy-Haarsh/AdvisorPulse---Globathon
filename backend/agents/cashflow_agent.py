"""CashFlow Agent — contributions/withdrawals (not investment returns)."""
from __future__ import annotations

from analytics.portfolio import DataStore
from domain.evidence import ConfidenceLevel, envelope, insufficient
from agents.schemas import AgentFinding


def run(store: DataStore, investor_id: str) -> AgentFinding:
    cf = store.cashflows[store.cashflows["investor_id"] == investor_id]
    if cf.empty:
        return AgentFinding(
            agent="CashFlow",
            claim="Insufficient cashflow data",
            supported=False,
            rejected_reason="No cashflows",
            evidence=insufficient("CashFlow agent", ["cashflows"]),
        )
    contrib = float(cf[cf["flow_type"] == "contribution"]["amount"].astype(float).sum())
    wd = float(cf[cf["flow_type"] == "withdrawal"]["amount"].astype(float).sum())
    claim = (
        f"Contributions {contrib:,.0f}; withdrawals {wd:,.0f} "
        f"(cash-flow layer — not investment TWR)"
    )
    return AgentFinding(
        agent="CashFlow",
        claim=claim,
        metrics={"contributions": contrib, "withdrawals": wd, "net": contrib + wd},
        evidence=envelope(
            claim,
            confidence=ConfidenceLevel.VERIFIED,
            evidence=[
                {
                    "source": "synthetic_cashflows.csv",
                    "record_ids": cf["cashflow_id"].astype(str).tolist()[:8],
                    "detail": "Signed amounts; withdrawal negative",
                }
            ],
            limitations=["Never interpret cashflows as portfolio returns."],
        ),
        supported=True,
    )
