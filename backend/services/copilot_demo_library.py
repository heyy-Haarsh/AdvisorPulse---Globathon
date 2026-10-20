"""
Seeded Copilot demo question library for Globathon presentations.

Contains question text, scenario IDs, expected analysis routes, and follow-up
templates — NOT hardcoded financial facts. Client-specific numbers always come
from validated services at query time.
"""
from __future__ import annotations

from typing import Any

# Categories shown on the Copilot welcome screen
CATEGORIES: list[dict[str, Any]] = [
    {
        "id": "attention",
        "label": "Client Attention",
        "description": "Who needs attention and why",
    },
    {
        "id": "portfolio",
        "label": "Portfolio & Goals",
        "description": "Goal path, allocation, and performance evidence",
    },
    {
        "id": "advice",
        "label": "Advice & Follow-ups",
        "description": "Unresolved recommendations and commitments",
    },
    {
        "id": "meeting",
        "label": "Meeting Preparation",
        "description": "Briefs, questions, and open actions",
    },
]

# Demo scenarios for the Demo Scenarios panel
SCENARIOS: list[dict[str, Any]] = [
    {
        "id": "critical_client",
        "group": "Critical client",
        "title": "Critical client investigation",
        "question": "Why is DEMO-INV-001 marked Critical?",
        "expected_intent": "priority",
        "expected_function": "score_investor",
        "category": "attention",
        "default_client": "DEMO-INV-001",
    },
    {
        "id": "overlooked",
        "group": "Overlooked client",
        "title": "Overlooked-client discovery",
        "question": "Which clients outside the frequently reviewed group need attention?",
        "expected_intent": "less_observed",
        "expected_function": "attention_engine_less_observed",
        "category": "attention",
        "default_client": None,
    },
    {
        "id": "planned_withdrawal",
        "group": "Critical client",
        "title": "Planned-withdrawal explanation",
        "question": "Why wasn't Arjun Mehta escalated even though his AUM declined?",
        "expected_intent": "priority",
        "expected_function": "score_investor",
        "category": "attention",
        "default_client": "DEMO-INV-002",
    },
    {
        "id": "goal_trajectory",
        "group": "Portfolio and goals",
        "title": "Goal trajectory review",
        "question": "Which clients are falling behind their financial goals, and why?",
        "expected_intent": "goal_behind_book",
        "expected_function": "rank_book_goal_deviation",
        "category": "portfolio",
        "default_client": None,
    },
    {
        "id": "unresolved_advice",
        "group": "Advice outcomes",
        "title": "Unresolved advice and commitments",
        "question": "Which clients have unresolved recommendations or overdue commitments?",
        "expected_intent": "unresolved_book",
        "expected_function": "overdue_advice_scan",
        "category": "advice",
        "default_client": None,
    },
    {
        "id": "meeting_prep",
        "group": "Meeting preparation",
        "title": "Meeting preparation",
        "question": "Prepare me for my next meeting with DEMO-INV-001.",
        "expected_intent": "meeting_prep",
        "expected_function": "pre_meeting_pack",
        "category": "meeting",
        "default_client": "DEMO-INV-001",
    },
    {
        "id": "insufficient_outcome",
        "group": "Advice outcomes",
        "title": "Insufficient-data demonstration",
        "question": "Can you conclusively determine whether this client's earlier recommendation succeeded?",
        "expected_intent": "insufficient_outcome",
        "expected_function": "advice_outcome_report",
        "category": "advice",
        "default_client": "DEMO-INV-001",
    },
    {
        "id": "whatif_sip",
        "group": "What-if analysis",
        "title": "Hypothetical contribution analysis",
        "question": "What would happen to this goal if DEMO-INV-001 increased their monthly SIP by 10000?",
        "expected_intent": "whatif",
        "expected_function": "simulate",
        "category": "portfolio",
        "default_client": "DEMO-INV-001",
    },
    {
        "id": "patterns",
        "group": "Overlooked client",
        "title": "Cross-client patterns",
        "question": "What common patterns are emerging across the clients who need attention?",
        "expected_intent": "patterns",
        "expected_function": "discover_patterns",
        "category": "attention",
        "default_client": None,
    },
    {
        "id": "data_quality",
        "group": "Data quality",
        "title": "Data quality investigation",
        "question": "Which data-quality issues could affect our financial analysis?",
        "expected_intent": "data_quality",
        "expected_function": "txn_quality_exceptions",
        "category": "portfolio",
        "default_client": None,
    },
]

# Quick-start prompts by category (clickable in UI)
QUICK_START: dict[str, list[str]] = {
    "attention": [
        "Who needs attention today?",
        "Find overlooked clients who may need a review.",
        "Why is DEMO-INV-001 marked Critical?",
        "What are the main reasons behind DEMO-INV-001's priority score?",
        "Which clients have overdue follow-ups?",
    ],
    "portfolio": [
        "Which clients are falling behind their expected goal trajectory?",
        "Why did DEMO-INV-001's portfolio path deviate from expected?",
        "Which allocation deviations deserve a review for DEMO-INV-001?",
        "What information is missing to assess DEMO-INV-001's financial position?",
        "Show me the available portfolio performance analysis for DEMO-INV-001.",
    ],
    "advice": [
        "Which previous recommendations have unresolved follow-ups?",
        "What outcome was expected from the previous advice for DEMO-INV-001?",
        "Can you conclusively determine whether this client's earlier recommendation succeeded?",
        "Which clients need an advisor to revisit an earlier recommendation?",
    ],
    "meeting": [
        "Prepare a meeting brief for DEMO-INV-001.",
        "What should I discuss in the next meeting with DEMO-INV-001?",
        "Summarize DEMO-INV-001's recent notes and commitments.",
        "Which follow-up actions are still outstanding for DEMO-INV-001?",
    ],
}


def catalog() -> dict[str, Any]:
    return {
        "categories": CATEGORIES,
        "scenarios": SCENARIOS,
        "quick_start": QUICK_START,
        "welcome": {
            "title": "Advisor Copilot",
            "subtitle": (
                "Understand your clients, investigate portfolio changes, and prepare your next "
                "review using verified evidence from your client book."
            ),
        },
        "is_demo": True,
        "note": (
            "Seeded questions invoke the same validated analysis functions as free-form queries. "
            "Financial figures are never hardcoded in this library."
        ),
    }


def match_scenario(query: str) -> dict[str, Any] | None:
    q = (query or "").strip().lower()
    for s in SCENARIOS:
        if s["question"].strip().lower() == q:
            return s
    # Fuzzy: significant overlap with scenario question
    for s in SCENARIOS:
        key = s["question"].lower()
        # Match distinctive phrases
        if s["id"] == "planned_withdrawal" and "arjun" in q and ("escalat" in q or "aum" in q):
            return s
        if s["id"] == "overlooked" and ("overlook" in q or "less-observed" in q or "frequently reviewed" in q):
            return s
        if s["id"] == "insufficient_outcome" and "conclusively" in q and "recommendation" in q:
            return s
        if s["id"] == "critical_client" and "demo-inv-001" in q and "critical" in q:
            return s
        if s["id"] == "meeting_prep" and "meeting" in q and ("demo-inv-001" in q or "prepare" in q):
            if "prepare" in q:
                return s
        if key[:40] in q or q in key:
            return s
    return None
