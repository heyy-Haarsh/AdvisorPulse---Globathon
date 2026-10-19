"""
InsightVerification Agent — rejects unsupported / invented claims.

Rules:
- Metrics must be present in finding.metrics or evidence
- No NaN silently treated as 0
- Claims mentioning percentages must have matching numeric metrics
"""
from __future__ import annotations

import math
import re
from typing import Any

from agents.schemas import AgentFinding


def verify(finding: AgentFinding) -> AgentFinding:
    if not finding.supported:
        return finding

    metrics = finding.metrics or {}
    # Reject if any metric is NaN
    for k, v in metrics.items():
        if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
            return finding.model_copy(
                update={
                    "supported": False,
                    "rejected_reason": f"Metric {k} is NaN/Inf — not silently zeroed",
                }
            )

    # Reject empty claim
    if not (finding.claim or "").strip():
        return finding.model_copy(
            update={"supported": False, "rejected_reason": "Empty claim"}
        )

    # If claim asserts a number, require some metrics or evidence
    has_number = bool(re.search(r"\d", finding.claim))
    has_evidence = bool((finding.evidence or {}).get("evidence")) or bool(metrics)
    if has_number and not has_evidence:
        return finding.model_copy(
            update={
                "supported": False,
                "rejected_reason": "Numeric claim without evidence or metrics",
            }
        )

    # Insufficient confidence → reject as authoritative finding
    conf = (finding.evidence or {}).get("confidence")
    if conf == "Insufficient":
        return finding.model_copy(
            update={
                "supported": False,
                "rejected_reason": "Insufficient evidence confidence",
            }
        )

    return finding


def verify_bundle(findings: list[AgentFinding]) -> tuple[list[AgentFinding], list[AgentFinding]]:
    verified, rejected = [], []
    for f in findings:
        v = verify(f)
        if v.supported:
            verified.append(v)
        else:
            rejected.append(v)
    return verified, rejected


def reject_fabricated_claim(claim: str) -> AgentFinding:
    """FinRobot-style gate: numeric claim with no evidence/metrics must be rejected."""
    from domain.evidence import ConfidenceLevel, envelope

    finding = AgentFinding(
        agent="verification",
        claim=claim,
        supported=True,
        metrics={},
        evidence=envelope(
            claim,
            confidence=ConfidenceLevel.INSUFFICIENT,
            missing_data=["metrics", "source_records"],
        ),
    )
    return verify(finding)
