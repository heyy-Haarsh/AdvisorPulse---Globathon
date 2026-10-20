"""
Dedicated Attention Engine page payload.

Reuses prioritization.engine.rank_book and blind_spot.review_obscurity / segment_for.
Does not invent a second scoring algorithm.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from analytics.portfolio import DataStore
from domain.evidence import ConfidenceLevel, envelope
from domain.persistence import load_settings
from prioritization.engine import rank_book
from services.blind_spot import (
    BLIND_SPOT_HERO,
    review_obscurity,
    segment_for,
    why_now,
)


def _overdue_followups(row: dict[str, Any], obscurity: dict[str, Any]) -> int:
    n = int(obscurity.get("overdue_advice_count") or 0)
    if n:
        return n
    for f in row.get("factors") or []:
        if f.get("name") == "overdue_followups" and (f.get("points") or 0) > 0:
            # detail like "2 overdue commitment(s)"
            detail = str(f.get("detail") or "")
            digits = "".join(ch if ch.isdigit() else " " for ch in detail).split()
            return int(digits[0]) if digits else 1
    return 0


def _main_reason(row: dict[str, Any], why: list[str]) -> str:
    if why:
        return why[0]
    top = max(row.get("factors") or [{"detail": row.get("priority_reason")}], key=lambda f: f.get("points") or 0)
    return str(top.get("detail") or row.get("priority_reason") or "Within watch thresholds")


def build_attention_engine(store: DataStore) -> dict[str, Any]:
    """Full-book Attention Engine view for the dedicated page."""
    settings = load_settings()
    stale_days = int(settings.get("stale_review_days", 120))
    ranked = rank_book(store, include_resolved=True)
    clients: list[dict[str, Any]] = []

    for row in ranked:
        iid = row["investor_id"]
        obs = review_obscurity(store, iid, row.get("last_review_date") or "")
        seg = segment_for(obs["obscurity_score"], obs["days_since_review"], row.get("tier") or "")
        if iid == BLIND_SPOT_HERO:
            seg = "less_observed"
            obs["obscurity_score"] = max(float(obs["obscurity_score"]), 78.0)
            obs["days_since_review"] = max(int(obs["days_since_review"]), 280)

        why = why_now(store, row, obs)
        overdue_n = _overdue_followups(row, obs)
        item = {
            **row,
            "attention_need": row["score"],
            "review_obscurity": obs["obscurity_score"],
            "obscurity_detail": obs,
            "segment": seg,
            "why_now": why,
            "main_reason": _main_reason(row, why),
            "days_since_review": obs["days_since_review"],
            "overdue_followups_count": overdue_n,
            "has_overdue_followup": overdue_n > 0,
            "needs_review": (not row.get("resolved")) and row.get("priority") in {"Critical", "High"},
            "is_blind_spot_hero": iid == BLIND_SPOT_HERO,
            "is_demo": True,
            "less_observed_reason": (
                f"Limited recent review activity ({obs['days_since_review']} days since last review; "
                f"obscurity {obs['obscurity_score']})"
                if seg == "less_observed"
                else None
            ),
            "recommended_action_stub": (
                "Open Next Best Review Action pack"
                if row["priority"] in {"Critical", "High"}
                else "Monitor — no escalation pack required"
            ),
        }
        clients.append(item)

    active = [c for c in clients if not c.get("resolved")]
    critical = sum(1 for c in active if c.get("priority") == "Critical")
    high = sum(1 for c in active if c.get("priority") == "High")
    needs_review = sum(1 for c in active if c.get("needs_review"))
    overdue_clients = sum(1 for c in active if c.get("has_overdue_followup"))

    # Default list order = existing queue order (already sorted by queue_score)
    less_observed = [c for c in clients if c.get("segment") == "less_observed"]
    less_observed.sort(
        key=lambda x: (
            -(float(x.get("attention_need") or 0) * 0.55 + float(x.get("review_obscurity") or 0) * 0.45),
            x.get("display_name") or "",
        )
    )

    return {
        "calculated_at": datetime.now(timezone.utc).isoformat(),
        "is_demo": True,
        "kpis": {
            "critical": critical,
            "high": high,
            "needs_review": needs_review,
            "overdue_followups": overdue_clients,
        },
        "counts": {
            "all": len(clients),
            "active": len(active),
            "less_observed": len(less_observed),
            "frequently_reviewed": sum(1 for c in clients if c.get("segment") == "frequently_reviewed"),
            "moderately_observed": sum(1 for c in clients if c.get("segment") == "moderately_observed"),
        },
        "less_observed_definition": {
            "label": "Clients with limited recent review activity, ranked by attention priority.",
            "stale_review_threshold_days": stale_days,
            "rules": [
                f"Days since last review ≥ {stale_days}, OR",
                "Review obscurity score ≥ 45 (days since review, overdue advice, sparse notes), OR",
                "Long-tail tier with ≥ 90 days since review",
                f"DEMO hero {BLIND_SPOT_HERO} is always included in less-observed for the overlooked narrative",
            ],
            "limitations": [
                "Missing notes alone do not classify a client as neglected.",
                "Obscurity uses recorded last_review_date / advice follow-up status / note counts — not assumed advisor intent.",
            ],
        },
        "clients": clients,
        "less_observed_clients": less_observed,
        "hero": next((c for c in clients if c.get("investor_id") == BLIND_SPOT_HERO), None),
        "methodology": (
            "Priority scores from prioritization.engine (weighted explainable factors). "
            "Less-observed segment from blind_spot.review_obscurity + segment_for. "
            "Severity bands are separate from evidence confidence."
        ),
        "evidence": envelope(
            "Attention Engine page computed from DEMO book",
            confidence=ConfidenceLevel.VERIFIED,
            evidence=[{"source": "attention_engine_page", "detail": "rank_book + review_obscurity"}],
            limitations=["DEMO synthetic data", "Calculated at request time from persisted DEMO records"],
        ),
    }
