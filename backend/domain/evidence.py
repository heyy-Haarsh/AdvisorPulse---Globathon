"""
Unified evidence & confidence layer (Feature 11).

All modules attach EvidenceEnvelope so insights are Verified / Limited / Insufficient,
never silent fabrications. Deterministic numbers only — no LLM-invented metrics.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ConfidenceLevel(str, Enum):
    VERIFIED = "Verified"
    LIMITED = "Limited"
    INSUFFICIENT = "Insufficient"


class EvidenceItem(BaseModel):
    source: str
    record_ids: list[str] = Field(default_factory=list)
    as_of: str | None = None
    detail: str = ""
    freshness_days: int | None = None


class EvidenceEnvelope(BaseModel):
    confidence: ConfidenceLevel
    severity: str = "info"  # critical | high | medium | low | info
    claim: str
    evidence: list[EvidenceItem] = Field(default_factory=list)
    missing_data: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)
    computed_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    is_hypothetical: bool = False

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump()


def classify_confidence(
    *,
    has_required: bool,
    evidence_count: int,
    freshness_days: int | None = None,
    stale_after: int = 45,
    incomplete_fields: list[str] | None = None,
) -> ConfidenceLevel:
    missing = incomplete_fields or []
    if not has_required or evidence_count == 0:
        return ConfidenceLevel.INSUFFICIENT
    stale = freshness_days is not None and freshness_days >= stale_after
    if missing or stale or evidence_count < 2:
        return ConfidenceLevel.LIMITED
    return ConfidenceLevel.VERIFIED


def envelope(
    claim: str,
    *,
    confidence: ConfidenceLevel | str,
    severity: str = "info",
    evidence: list[dict[str, Any] | EvidenceItem] | None = None,
    missing_data: list[str] | None = None,
    limitations: list[str] | None = None,
    next_steps: list[str] | None = None,
    is_hypothetical: bool = False,
) -> dict[str, Any]:
    items: list[EvidenceItem] = []
    for e in evidence or []:
        if isinstance(e, EvidenceItem):
            items.append(e)
        else:
            items.append(EvidenceItem(**e))
    conf = (
        confidence
        if isinstance(confidence, ConfidenceLevel)
        else ConfidenceLevel(confidence)
    )
    return EvidenceEnvelope(
        confidence=conf,
        severity=severity,
        claim=claim,
        evidence=items,
        missing_data=missing_data or [],
        limitations=limitations or [],
        next_steps=next_steps or [],
        is_hypothetical=is_hypothetical,
    ).to_dict()


def insufficient(claim: str, missing: list[str], **kwargs: Any) -> dict[str, Any]:
    return envelope(
        claim,
        confidence=ConfidenceLevel.INSUFFICIENT,
        missing_data=missing,
        limitations=kwargs.get("limitations", ["Insufficient data for this claim."]),
        next_steps=kwargs.get("next_steps", ["Gather missing records before acting."]),
        severity=kwargs.get("severity", "info"),
    )


def today_iso() -> str:
    return date.today().isoformat()
