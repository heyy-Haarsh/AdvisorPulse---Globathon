"""
Alert Quality Lab — compare Pulse ranking vs CRM-ish baseline on labeled DEMO scenarios.
Metrics are computed from labels; never fabricated.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from analytics.portfolio import DataStore, TODAY
from domain.evidence import ConfidenceLevel, envelope
from prioritization.engine import rank_book, score_investor

ROOT = Path(__file__).resolve().parents[2]
LABELS_PATH = ROOT / "data" / "eval" / "labeled_scenarios.json"


def load_labels() -> dict[str, Any]:
    if not LABELS_PATH.exists():
        return {"labels": []}
    return json.loads(LABELS_PATH.read_text(encoding="utf-8"))


def _parse_days_since(last_review: str) -> int:
    from datetime import date

    try:
        d = date.fromisoformat(str(last_review)[:10])
        return (TODAY - d).days
    except Exception:
        return 999


def baseline_rank(store: DataStore) -> list[dict[str, Any]]:
    """
    CRM-ish queue: high-visibility first, then by days since last review (stale first).
    Does not use goal deviation or Pulse score.
    """
    rows = []
    for _, inv in store.investors.iterrows():
        iid = str(inv["investor_id"])
        days = _parse_days_since(str(inv.get("last_review_date") or ""))
        tier = str(inv.get("tier") or "")
        # Prefer high_visibility in baseline (advisor's usual book)
        tier_boost = 1000 if tier == "high_visibility" else 0
        rows.append(
            {
                "investor_id": iid,
                "display_name": str(inv["display_name"]),
                "tier": tier,
                "days_since_review": days,
                "baseline_score": tier_boost + days,
                "method": "crm_review_date_plus_tier",
            }
        )
    rows.sort(key=lambda x: (-x["baseline_score"], x["display_name"]))
    return rows


def precision_at_k(ranked_ids: list[str], material_ids: set[str], k: int) -> float:
    top = ranked_ids[:k]
    if not top:
        return 0.0
    hits = sum(1 for i in top if i in material_ids)
    return hits / len(top)


def recall_at_k(ranked_ids: list[str], material_ids: set[str], k: int) -> float:
    if not material_ids:
        return 0.0
    top = set(ranked_ids[:k])
    return len(top & material_ids) / len(material_ids)


def false_positive_rate(
    ranked_ids: list[str],
    false_alarm_ids: set[str],
    k: int,
) -> float:
    """Share of top-k that are labeled false_alarm_context."""
    top = ranked_ids[:k]
    if not top:
        return 0.0
    return sum(1 for i in top if i in false_alarm_ids) / len(top)


def evidence_coverage(store: DataStore, investor_ids: list[str]) -> float:
    if not investor_ids:
        return 0.0
    covered = 0
    for iid in investor_ids:
        pri = score_investor(store, iid)
        ev = pri.get("evidence") or {}
        items = ev.get("evidence") or []
        if items and pri.get("confidence") in {"Verified", "Limited"}:
            covered += 1
    return covered / len(investor_ids)


def evaluate(store: DataStore) -> dict[str, Any]:
    meta = load_labels()
    labels = meta.get("labels") or []
    by_id = {x["investor_id"]: x for x in labels}
    material = {x["investor_id"] for x in labels if x["label"] == "material_review_needed"}
    false_alarms = {x["investor_id"] for x in labels if x["label"] == "false_alarm_context"}

    pulse = rank_book(store, include_resolved=True)
    # Active queue order (resolved demoted already via queue_score)
    pulse_ids = [r["investor_id"] for r in pulse]
    baseline = baseline_rank(store)
    baseline_ids = [r["investor_id"] for r in baseline]

    # Where do material cases sit?
    def ranks(ids: list[str], targets: set[str]) -> dict[str, int]:
        out = {}
        for t in targets:
            try:
                out[t] = ids.index(t) + 1
            except ValueError:
                out[t] = -1
        return out

    pulse_metrics = {
        "precision_at_10": round(precision_at_k(pulse_ids, material, 10), 4),
        "precision_at_20": round(precision_at_k(pulse_ids, material, 20), 4),
        "recall_at_20": round(recall_at_k(pulse_ids, material, 20), 4),
        "false_positive_rate_at_20": round(false_positive_rate(pulse_ids, false_alarms, 20), 4),
        "evidence_coverage_top_20": round(evidence_coverage(store, pulse_ids[:20]), 4),
        "material_ranks": ranks(pulse_ids, material),
        "false_alarm_ranks": ranks(pulse_ids, false_alarms),
    }
    baseline_metrics = {
        "precision_at_10": round(precision_at_k(baseline_ids, material, 10), 4),
        "precision_at_20": round(precision_at_k(baseline_ids, material, 20), 4),
        "recall_at_20": round(recall_at_k(baseline_ids, material, 20), 4),
        "false_positive_rate_at_20": round(false_positive_rate(baseline_ids, false_alarms, 20), 4),
        "material_ranks": ranks(baseline_ids, material),
        "false_alarm_ranks": ranks(baseline_ids, false_alarms),
    }

    # Side-by-side top 20
    pulse_top = [
        {
            "rank": i + 1,
            "investor_id": r["investor_id"],
            "display_name": r["display_name"],
            "priority": r["priority"],
            "score": r["score"],
            "tier": r["tier"],
            "label": (by_id.get(r["investor_id"]) or {}).get("label"),
        }
        for i, r in enumerate(pulse[:20])
    ]
    baseline_top = [
        {
            "rank": i + 1,
            "investor_id": r["investor_id"],
            "display_name": r["display_name"],
            "tier": r["tier"],
            "days_since_review": r["days_since_review"],
            "label": (by_id.get(r["investor_id"]) or {}).get("label"),
        }
        for i, r in enumerate(baseline[:20])
    ]

    return {
        "n_labeled": len(labels),
        "n_material": len(material),
        "n_false_alarm": len(false_alarms),
        "labels": labels,
        "pulse": pulse_metrics,
        "baseline": baseline_metrics,
        "pulse_top_20": pulse_top,
        "baseline_top_20": baseline_top,
        "methodology": (
            "Baseline = high_visibility preferred, then days since last review. "
            "Pulse = explainable Attention Engine (queue_score). "
            "Precision/Recall use labeled DEMO scenarios only (n="
            f"{len(labels)}). Do not generalize beyond this fixture."
        ),
        "evidence": envelope(
            "Alert quality metrics from labeled DEMO scenarios",
            confidence=ConfidenceLevel.VERIFIED,
            evidence=[{"source": "labeled_scenarios.json", "detail": str(LABELS_PATH)}],
            limitations=[
                "Small labeled DEMO set — not a production pilot result",
                "Labels are scenario authoring, not advisor-verified production outcomes",
            ],
        ),
        "is_demo": True,
    }
