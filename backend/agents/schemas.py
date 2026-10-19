"""Shared agent I/O schemas."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class AgentFinding(BaseModel):
    agent: str
    claim: str
    metrics: dict[str, Any] = Field(default_factory=dict)
    evidence: dict[str, Any] = Field(default_factory=dict)
    supported: bool = True
    rejected_reason: str | None = None


class AgentBundle(BaseModel):
    investor_id: str
    findings: list[AgentFinding] = Field(default_factory=list)
    verified: list[AgentFinding] = Field(default_factory=list)
    rejected: list[AgentFinding] = Field(default_factory=list)
    merged_summary: str = ""
    is_demo: bool = True
