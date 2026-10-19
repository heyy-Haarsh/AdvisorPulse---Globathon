"""
NL Advisor Copilot (Feature 7).

Maps natural language → validated analysis functions (NOT arbitrary SQL).
Cites records. Respects advisor-client access. No invented metrics.
"""
from __future__ import annotations

import re
from typing import Any, Callable

from analytics.portfolio import DataStore
from domain.evidence import ConfidenceLevel, envelope, insufficient
from domain.persistence import audit, load_settings
from prioritization.engine import score_investor
from services.advice_outcome import advice_outcome_report
from services.client_summary import build_structured_summary
from services.drift import detect_drift
from services.patterns import discover_patterns
from services.whatif import simulate


ALLOWED_FUNCTIONS: dict[str, str] = {
    "priority": "score_investor",
    "summary": "build_structured_summary",
    "drift": "detect_drift",
    "advice_outcome": "advice_outcome_report",
    "whatif": "simulate",
    "patterns": "discover_patterns",
    "goal": "goal_snapshot",
}


def _accessible(investor_id: str) -> bool:
    settings = load_settings()
    allowed = settings.get("accessible_clients")
    if allowed is None:
        return True  # demo: all clients
    return investor_id in allowed


def _extract_investor_id(text: str, context_id: str | None) -> str | None:
    m = re.search(r"DEMO-INV-[\w]+", text, re.I)
    if m:
        return m.group(0).upper().replace("DEMO-INV-", "DEMO-INV-")
    # normalize case
    m = re.search(r"(demo-inv-[\w]+)", text, re.I)
    if m:
        parts = m.group(1).split("-")
        return f"DEMO-INV-{parts[-1].upper()}" if len(parts) >= 3 else m.group(1).upper()
    return context_id


def route_query(
    store: DataStore,
    query: str,
    *,
    context_investor_id: str | None = None,
    advisor_id: str = "DEMO-ADV-USER-01",
) -> dict[str, Any]:
    q = (query or "").strip()
    if not q:
        return {
            "error": "Empty query",
            "evidence": insufficient("Copilot", ["query"]),
        }

    investor_id = _extract_investor_id(q, context_investor_id)
    lower = q.lower()

    # Access control
    if investor_id and not _accessible(investor_id):
        audit("copilot_denied", {"advisor_id": advisor_id, "investor_id": investor_id})
        return {
            "denied": True,
            "message": "Access denied: advisor not permitted for this client.",
            "evidence": envelope(
                "ACL denial",
                confidence=ConfidenceLevel.VERIFIED,
                evidence=[{"source": "access_control", "detail": "advisor-client boundary"}],
            ),
            "is_demo": True,
        }

    intent = _map_intent(lower)
    audit("copilot_query", {"advisor_id": advisor_id, "intent": intent, "investor_id": investor_id})

    handlers: dict[str, Callable[..., dict[str, Any]]] = {
        "priority": lambda: _wrap("priority", score_investor(store, investor_id), investor_id),
        "summary": lambda: _wrap("summary", build_structured_summary(store, investor_id), investor_id),
        "drift": lambda: _wrap("drift", detect_drift(store, investor_id), investor_id),
        "advice_outcome": lambda: _wrap("advice_outcome", advice_outcome_report(store, investor_id), investor_id),
        "whatif": lambda: _wrap(
            "whatif",
            simulate(
                store,
                investor_id,
                sip_delta=_parse_sip_delta(lower),
                return_delta_pp=_parse_return_delta(lower),
            ),
            investor_id,
        ),
        "patterns": lambda: _wrap("patterns", discover_patterns(store), None),
        "goal": lambda: _goal(store, investor_id),
    }

    if intent in {"priority", "summary", "drift", "advice_outcome", "whatif", "goal"} and not investor_id:
        return {
            "intent": intent,
            "message": "Specify a client (e.g. DEMO-INV-001) or open a client context.",
            "allowed_functions": list(ALLOWED_FUNCTIONS.keys()),
            "evidence": insufficient("Copilot client context", ["investor_id"]),
            "is_demo": True,
        }

    if investor_id and investor_id not in set(store.investors["investor_id"].astype(str)):
        return {
            "error": "Investor not found",
            "investor_id": investor_id,
            "evidence": insufficient("Copilot", ["valid investor_id"]),
            "is_demo": True,
        }

    result = handlers[intent]()
    result["query"] = q
    result["intent"] = intent
    result["mapped_function"] = ALLOWED_FUNCTIONS[intent]
    result["allowed_functions"] = list(ALLOWED_FUNCTIONS.keys())
    result["no_arbitrary_sql"] = True
    result["is_demo"] = True
    return result


def _wrap(intent: str, data: dict[str, Any], investor_id: str | None) -> dict[str, Any]:
    return {
        "investor_id": investor_id,
        "result": data,
        "citations": _citations(data),
        "evidence": data.get("evidence")
        or envelope(
            f"Result from {intent}",
            confidence=ConfidenceLevel.LIMITED,
            evidence=[{"source": ALLOWED_FUNCTIONS[intent], "record_ids": [investor_id] if investor_id else []}],
            limitations=["Copilot only calls validated analysis functions — no free-form SQL."],
        ),
        "is_demo": True,
    }


def _goal(store: DataStore, investor_id: str) -> dict[str, Any]:
    from analytics.portfolio import investor_snapshot

    snap = investor_snapshot(store, investor_id)
    if snap.get("error"):
        return {"error": snap["error"], "evidence": insufficient("Goal", ["goal"])}
    gp = snap["goal_progress"]
    return _wrap(
        "goal",
        {
            "goal_progress": gp,
            "evidence": envelope(
                f"{gp['goal_name']}: {gp['deviation_pct_vs_expected']:+.1f}% vs expected",
                confidence=ConfidenceLevel.VERIFIED,
                evidence=[{"source": "synthetic_goals.csv", "detail": gp["methodology"]}],
            ),
            "is_demo": True,
        },
        investor_id,
    )


def _citations(data: dict[str, Any]) -> list[str]:
    cites: list[str] = []
    ev = data.get("evidence") or {}
    for item in ev.get("evidence") or []:
        src = item.get("source")
        if src:
            cites.append(src)
        for rid in item.get("record_ids") or []:
            cites.append(str(rid))
    return list(dict.fromkeys(cites))[:20]


def _map_intent(lower: str) -> str:
    if any(w in lower for w in ("pattern", "cohort", "across client", "book-wide", "book wide")):
        return "patterns"
    if any(w in lower for w in ("what if", "what-if", "simulate", "scenario", "if i increase sip")):
        return "whatif"
    if any(w in lower for w in ("drift", "allocation drift", "hidden")):
        return "drift"
    if any(w in lower for w in ("advice", "outcome", "did the advice", "follow-up")):
        return "advice_outcome"
    if any(
        w in lower
        for w in (
            "priority",
            "attention",
            "why critical",
            "critical",
            "score",
            "why is",
            "escalat",
        )
    ):
        return "priority"
    if any(w in lower for w in ("goal", "expected path", "behind")):
        return "goal"
    if any(w in lower for w in ("summary", "overview", "how is", "status")):
        return "summary"
    return "summary"


def _parse_sip_delta(lower: str) -> float:
    m = re.search(r"(?:increase|raise|add)\s+sip\s+(?:by\s+)?(\d[\d,]*)", lower)
    if m:
        return float(m.group(1).replace(",", ""))
    m = re.search(r"sip\s*\+\s*(\d[\d,]*)", lower)
    if m:
        return float(m.group(1).replace(",", ""))
    return 10000.0 if "sip" in lower else 0.0


def _parse_return_delta(lower: str) -> float:
    m = re.search(r"(?:return|expected)\s+(?:by\s+)?([+-]?\d+(?:\.\d+)?)\s*%?", lower)
    if m and "sip" not in lower[max(0, m.start() - 10) : m.start()]:
        return float(m.group(1))
    return 0.0
