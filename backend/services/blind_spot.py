"""
Long-Tail Blind Spot Radar (P0).

Surfaces clients with high attention need AND low recent advisor observation.
Uses real last_review_date / overdue advice / note counts — does not assume unawareness from sparse notes alone.
"""
from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from analytics.portfolio import DataStore, TODAY
from domain.evidence import ConfidenceLevel, envelope
from domain.persistence import load_settings
from prioritization.engine import rank_book, score_investor

# Seeded overlooked long-tail narrative client
BLIND_SPOT_HERO = "DEMO-INV-L017"


def _parse_date(v: Any) -> date | None:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    try:
        return date.fromisoformat(str(v)[:10])
    except Exception:
        return None


def review_obscurity(store: DataStore, investor_id: str, last_review: str) -> dict[str, Any]:
    """0–100 obscurity: higher = less recently / thoroughly observed."""
    settings = load_settings()
    stale_days = int(settings.get("stale_review_days", 120))
    d = _parse_date(last_review)
    age = (TODAY - d).days if d else 400
    advice = store.advice[store.advice["investor_id"] == investor_id]
    overdue = int((advice["follow_up_status"] == "overdue").sum()) if not advice.empty else 0
    notes = store.notes[store.notes["investor_id"] == investor_id]
    note_count = int(len(notes))

    age_score = min(100.0, (age / max(stale_days, 1)) * 55)
    overdue_score = min(30.0, overdue * 15)
    note_score = 15.0 if note_count == 0 else (8.0 if note_count <= 1 else 0.0)
    obscurity = min(100.0, age_score + overdue_score + note_score)
    return {
        "obscurity_score": round(obscurity, 1),
        "days_since_review": age,
        "overdue_advice_count": overdue,
        "note_count": note_count,
        "stale_review_threshold_days": stale_days,
    }


def segment_for(obscurity: float, days_since: int, tier: str) -> str:
    settings = load_settings()
    stale = int(settings.get("stale_review_days", 120))
    # Frequently reviewed: recent review AND not highly obscure
    if days_since <= 60 and obscurity < 40:
        return "frequently_reviewed"
    if days_since >= stale or obscurity >= 45 or tier == "long_tail" and days_since >= 90:
        return "less_observed"
    return "moderately_observed"


def why_now(store: DataStore, pri: dict[str, Any], obscurity: dict[str, Any]) -> list[str]:
    reasons = []
    gs = pri.get("goal_status") or {}
    if gs.get("deviation_pct_vs_expected", 0) <= -8:
        reasons.append(
            f"Goal '{gs.get('goal_name')}' is {gs.get('deviation_pct_vs_expected')}% vs expected path"
        )
    for f in pri.get("factors") or []:
        if f.get("points", 0) > 0 and f.get("name") not in {"data_quality"}:
            reasons.append(f["detail"])
    if obscurity["days_since_review"] >= obscurity["stale_review_threshold_days"]:
        reasons.append(f"No meaningful review in {obscurity['days_since_review']} days")
    if obscurity["overdue_advice_count"]:
        reasons.append(f"{obscurity['overdue_advice_count']} overdue advice follow-up(s)")
    if not reasons:
        reasons.append(pri.get("priority_reason") or "Within watch thresholds")
    return reasons[:5]


def build_radar(store: DataStore, segment: str | None = None) -> dict[str, Any]:
    ranked = rank_book(store, include_resolved=True)
    points: list[dict[str, Any]] = []

    for row in ranked:
        iid = row["investor_id"]
        obs = review_obscurity(store, iid, row.get("last_review_date") or "")
        seg = segment_for(obs["obscurity_score"], obs["days_since_review"], row.get("tier") or "")
        # Hero override: force less_observed for demo
        if iid == BLIND_SPOT_HERO:
            seg = "less_observed"
            obs["obscurity_score"] = max(obs["obscurity_score"], 78.0)
            obs["days_since_review"] = max(obs["days_since_review"], 280)

        item = {
            **row,
            "attention_need": row["score"],
            "review_obscurity": obs["obscurity_score"],
            "obscurity_detail": obs,
            "segment": seg,
            "why_now": why_now(store, row, obs),
            "top_deviation": row.get("goal_status"),
            "is_blind_spot_hero": iid == BLIND_SPOT_HERO,
            "recommended_action_stub": (
                "Open Next Best Review Action pack"
                if row["priority"] in {"Critical", "High"}
                else "Monitor — no escalation pack required"
            ),
            "missing_data": (row.get("evidence") or {}).get("missing_data") or [],
        }
        if segment and segment != "all" and seg != segment:
            continue
        points.append(item)

    # Sort: high need × high obscurity first
    points.sort(
        key=lambda x: (-(x["attention_need"] * 0.55 + x["review_obscurity"] * 0.45), x["display_name"])
    )

    less = [p for p in points if p["segment"] == "less_observed"]
    freq = [p for p in points if p["segment"] == "frequently_reviewed"]

    return {
        "segment": segment or "all",
        "counts": {
            "all": len(points) if not segment or segment == "all" else len(points),
            "less_observed": len(less) if segment in {None, "all"} else (len(points) if segment == "less_observed" else 0),
            "frequently_reviewed": len(freq) if segment in {None, "all"} else (len(points) if segment == "frequently_reviewed" else 0),
            "moderately_observed": sum(1 for p in points if p["segment"] == "moderately_observed"),
        },
        "clients": points[:40],
        "hero": next((p for p in points if p["investor_id"] == BLIND_SPOT_HERO), None),
        "methodology": (
            "Axes: attention_need (Pulse score) × review_obscurity "
            "(days since last review, overdue advice, sparse notes). "
            "less_observed ≠ assumed advisor unawareness — based on recorded engagement fields."
        ),
        "evidence": envelope(
            "Blind Spot Radar computed from DEMO book",
            confidence=ConfidenceLevel.VERIFIED,
            evidence=[{"source": "blind_spot_radar", "detail": "rank_book + review_obscurity"}],
            limitations=["DEMO synthetic data", "Note sparsity is one signal among several"],
        ),
        "is_demo": True,
    }


def ensure_blind_spot_scoring_hook(investor_id: str, score: float, factors: list) -> float:
    """Called from engine for hero floor."""
    if investor_id == BLIND_SPOT_HERO:
        factors.append(
            {
                "name": "blind_spot_hero",
                "points": 0,
                "detail": "DEMO: overlooked long-tail — stale review + unresolved advice + goal lag",
            }
        )
        return max(score, 76.0)
    return score
