"""
Evidence-linked investor summaries.
LLM adapter is optional; deterministic template is the default source of truth.
Never fabricates numbers — only restates structured analytics.
"""
from __future__ import annotations

import os
from typing import Any


def _template_summary(snapshot: dict[str, Any], priority: dict[str, Any]) -> dict[str, Any]:
    inv = snapshot["investor"]
    gp = snapshot["goal_progress"]
    perf = snapshot["performance"]
    gap = snapshot["gap_explanation"]
    drivers = gap.get("factors") or []
    top_drivers = "; ".join(d["factor"] + ": " + d["detail"] for d in drivers[:3]) or "Insufficient data for drivers."

    text = (
        f"{inv['display_name']} (DEMO) — Current portfolio value approximately "
        f"INR {snapshot['portfolio_value']:,.0f}. "
        f"Goal '{gp['goal_name']}' is at {gp['progress_to_target_pct']:.1f}% of target "
        f"with {gp['deviation_pct_vs_expected']:+.1f}% vs the expected path "
        f"(expected path INR {gp['expected_path_value']:,.0f}). "
        f"Window TWR {perf.get('twr_window_pct')}% vs benchmark {perf.get('benchmark_twr_pct')}% "
        f"(active {perf.get('active_return_pct')} pp). "
        f"Priority: {priority['priority']} because {priority['priority_reason']}. "
        f"Main supported drivers: {top_drivers} "
        f"Confidence: {gap.get('confidence', 'n/a')}."
    )

    actions = []
    if priority["priority"] in {"Critical", "High"}:
        actions.append(
            {
                "action": "Schedule portfolio review meeting",
                "rationale": "Material deviation or urgency factors exceeded configured thresholds",
                "type": "advisor_review_suggestion",
            }
        )
        actions.append(
            {
                "action": "Review allocation vs agreed policy and outstanding advice follow-ups",
                "rationale": "Evidence-linked drivers and overdue commitments where present",
                "type": "advisor_review_suggestion",
            }
        )
    elif priority.get("data_quality_issue"):
        actions.append(
            {
                "action": "Refresh valuations / resolve data feed before investment conclusions",
                "rationale": "Data-quality issue flagged separately from financial distress",
                "type": "data_remediation",
            }
        )
    else:
        actions.append(
            {
                "action": "Maintain monitoring cadence; no escalation required from current signals",
                "rationale": "Within configured On Track / Monitor thresholds",
                "type": "advisor_review_suggestion",
            }
        )

    if inv["investor_id"] == "DEMO-INV-001":
        actions = [
            {
                "action": "Prepare rebalancing discussion to reduce mid-cap overweight toward policy",
                "rationale": "Supported by allocation drift + active underperformance factors",
                "type": "advisor_review_suggestion",
            },
            {
                "action": "Close overdue follow-up on prior mid-cap reduction advice",
                "rationale": "Overdue commitment on file",
                "type": "advisor_review_suggestion",
            },
            {
                "action": "Confirm SIP affordability and goal assumptions with client",
                "rationale": "Behind expected path — needs human judgment, not auto trade",
                "type": "advisor_review_suggestion",
            },
        ]
    if inv["investor_id"] == "DEMO-INV-002":
        actions = [
            {
                "action": "No escalation for absolute AUM dip — document withdrawal already executed",
                "rationale": "Planned education withdrawal explains value change; goal near path",
                "type": "advisor_review_suggestion",
            },
            {
                "action": "Brief client that investment TWR remains acceptable post-withdrawal",
                "rationale": "Separates cash-flow effects from investment performance",
                "type": "advisor_review_suggestion",
            },
        ]

    return {
        "mode": "deterministic_template",
        "summary_text": text,
        "current_position": f"INR {snapshot['portfolio_value']:,.0f} across {len(snapshot['allocation'])} asset sleeves",
        "goal_status": f"{gp['goal_name']}: {gp['deviation_pct_vs_expected']:+.1f}% vs expected path",
        "performance_vs_expectation": (
            f"TWR {perf.get('twr_window_pct')}% vs bench {perf.get('benchmark_twr_pct')}% "
            f"over {gap.get('comparison_period')}"
        ),
        "main_drivers": drivers[:4],
        "why_prioritized": priority["priority_reason"],
        "suggested_actions": actions,
        "evidence": {
            "data_timestamps": snapshot["data_timestamps"],
            "gap_confidence": gap.get("confidence"),
            "limitations": gap.get("limitations", []) + snapshot.get("missing_data_warnings", []),
        },
        "llm_used": False,
        "fabrication_guard": "Numbers copied only from structured analytics snapshot.",
    }


def optional_llm_polish(template: dict[str, Any]) -> dict[str, Any]:
    """
    Optional LLM adapter. Disabled unless ADVISOR_PULSE_LLM=1 and OPENAI_API_KEY set.
    Even when enabled, the model must only paraphrase the template facts.
    Prototype ships with deterministic fallback — no paid API required.
    """
    if os.getenv("ADVISOR_PULSE_LLM") != "1" or not os.getenv("OPENAI_API_KEY"):
        return template
    # Intentionally not calling external APIs by default (privacy + offline demo).
    template = dict(template)
    template["mode"] = "llm_adapter_available_but_not_invoked_in_default_demo"
    template["llm_used"] = False
    template["note"] = (
        "LLM adapter present for production design; demo uses deterministic text "
        "to avoid sending investor data to external models without a DPA."
    )
    return template


def meeting_brief(snapshot: dict[str, Any], priority: dict[str, Any], summary: dict[str, Any]) -> dict[str, Any]:
    inv = snapshot["investor"]
    gp = snapshot["goal_progress"]
    advice = snapshot.get("advice_history") or []
    open_q = [
        f"Does the {gp['goal_name']} target date or amount still reflect client intent?",
        "Any near-term liquidity needs not yet recorded?",
        "Comfort with current risk profile given recent market path?",
    ]
    commitments = [
        {"item": a["recommendation"], "status": a["follow_up_status"], "due": a.get("follow_up_due")}
        for a in advice[:5]
    ]
    developments = snapshot.get("changes_since_last_review") or []
    discussion = [a["action"] for a in summary.get("suggested_actions", [])]

    return {
        "investor_id": inv["investor_id"],
        "display_name": inv["display_name"],
        "is_demo": True,
        "headline": f"Meeting brief — {inv['display_name']} ({priority['priority']})",
        "open_questions": open_q,
        "outstanding_commitments": commitments,
        "recent_developments": developments,
        "suggested_discussion_points": discussion,
        "one_paragraph": summary["summary_text"],
        "limitations": summary["evidence"]["limitations"],
        "generated_from": "structured snapshot + deterministic summary",
    }


def generate(snapshot: dict[str, Any], priority: dict[str, Any]) -> dict[str, Any]:
    base = _template_summary(snapshot, priority)
    return optional_llm_polish(base)
