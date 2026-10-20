"""
NL Advisor Copilot (Feature 7) — context-aware, evidence-backed.

Maps natural language → validated analysis functions (NOT arbitrary SQL).
Cites records. Respects advisor-client access. No invented metrics.
Demo scenarios seed questions only — facts always come from live services.
"""
from __future__ import annotations

import re
from typing import Any, Callable

from analytics.portfolio import DataStore, investor_snapshot
from domain.evidence import ConfidenceLevel, envelope, insufficient
from domain.persistence import audit, load_commitments, load_settings
from prioritization.engine import rank_book, score_investor
from services import attention_engine_page, txn_quality
from services.advice_outcome import advice_outcome_report
from services.client_summary import build_structured_summary
from services import copilot_demo_library as demo_lib
from services.drift import detect_drift
from services.meetings import pre_meeting_pack
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
    "attention_book": "rank_book_attention",
    "less_observed": "attention_engine_less_observed",
    "goal_behind_book": "rank_book_goal_deviation",
    "unresolved_book": "overdue_advice_scan",
    "meeting_prep": "pre_meeting_pack",
    "data_quality": "txn_quality_exceptions",
    "insufficient_outcome": "advice_outcome_report",
}

NAME_HINTS: dict[str, str] = {
    "priya": "DEMO-INV-001",
    "priya sharma": "DEMO-INV-001",
    "arjun": "DEMO-INV-002",
    "arjun mehta": "DEMO-INV-002",
    "diya": "DEMO-INV-L017",
    "diya iyer": "DEMO-INV-L017",
}


def demo_catalog() -> dict[str, Any]:
    return demo_lib.catalog()


def _accessible(investor_id: str) -> bool:
    settings = load_settings()
    allowed = settings.get("accessible_clients")
    if allowed is None or allowed == []:
        return True
    return investor_id in allowed


def _extract_investor_id(
    text: str,
    context_id: str | None,
    conversation: dict[str, Any] | None,
) -> str | None:
    m = re.search(r"DEMO-INV-[\w]+", text, re.I)
    if m:
        raw = m.group(0)
        # Normalize DEMO-INV-L017 style
        parts = raw.split("-")
        if len(parts) >= 3:
            return f"DEMO-INV-{'-'.join(parts[2:]).upper()}"
        return raw.upper()

    lower = text.lower()
    for name, iid in NAME_HINTS.items():
        if name in lower:
            return iid

    # Pronouns / "this client" → conversation or page context
    if any(w in lower for w in ("them", "their", "this client", "the client", "that client")):
        if conversation and conversation.get("investor_id"):
            return str(conversation["investor_id"])
        if context_id:
            return context_id

    if conversation and conversation.get("investor_id") and any(
        w in lower for w in ("why", "prepare", "meeting", "outcome", "follow", "what if", "sip")
    ):
        # Keep prior client for follow-ups when no new ID stated
        if not re.search(r"demo-inv|which clients|who needs|across", lower):
            return str(conversation["investor_id"])

    return context_id


def route_query(
    store: DataStore,
    query: str,
    *,
    context_investor_id: str | None = None,
    advisor_id: str = "DEMO-ADV-USER-01",
    conversation_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    q = (query or "").strip()
    if not q:
        return {
            "error": "Empty query",
            "evidence": insufficient("Copilot", ["query"]),
            "is_demo": True,
        }

    conversation = dict(conversation_context or {})
    scenario = demo_lib.match_scenario(q)
    investor_id = _extract_investor_id(q, context_investor_id, conversation)
    if scenario and scenario.get("default_client") and not investor_id:
        investor_id = scenario["default_client"]

    lower = q.lower()

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
            "follow_ups": [],
            "links": [],
            "is_demo": True,
        }

    intent = (scenario or {}).get("expected_intent") or _map_intent(lower)
    audit(
        "copilot_query",
        {
            "advisor_id": advisor_id,
            "intent": intent,
            "investor_id": investor_id,
            "scenario_id": (scenario or {}).get("id"),
        },
    )

    handlers: dict[str, Callable[[], dict[str, Any]]] = {
        "priority": lambda: _handle_priority(store, investor_id, lower),
        "summary": lambda: _handle_summary(store, investor_id),
        "drift": lambda: _handle_drift(store, investor_id),
        "advice_outcome": lambda: _handle_advice(store, investor_id),
        "insufficient_outcome": lambda: _handle_insufficient_outcome(store, investor_id),
        "whatif": lambda: _handle_whatif(store, investor_id, lower),
        "patterns": lambda: _handle_patterns(store),
        "goal": lambda: _handle_goal(store, investor_id),
        "attention_book": lambda: _handle_attention_book(store),
        "less_observed": lambda: _handle_less_observed(store),
        "goal_behind_book": lambda: _handle_goal_behind(store),
        "unresolved_book": lambda: _handle_unresolved(store),
        "meeting_prep": lambda: _handle_meeting_prep(store, investor_id),
        "data_quality": lambda: _handle_data_quality(),
    }

    needs_client = {
        "priority",
        "summary",
        "drift",
        "advice_outcome",
        "insufficient_outcome",
        "whatif",
        "goal",
        "meeting_prep",
    }
    if intent in needs_client and not investor_id:
        return {
            "intent": intent,
            "mapped_function": ALLOWED_FUNCTIONS.get(intent),
            "message": "Specify a client (e.g. DEMO-INV-001 or Priya Sharma) or open a client context.",
            "answer": {
                "title": "Client context required",
                "summary": "This question needs a client ID or name.",
                "bullets": ["Example: Why is DEMO-INV-001 marked Critical?"],
                "claims": [],
            },
            "allowed_functions": list(ALLOWED_FUNCTIONS.keys()),
            "evidence": insufficient("Copilot client context", ["investor_id"]),
            "follow_ups": [
                "Who needs attention today?",
                "Why is DEMO-INV-001 marked Critical?",
                "Find overlooked clients who may need a review.",
            ],
            "links": [{"label": "Attention Engine", "href": "/attention-engine"}],
            "conversation_context": conversation,
            "is_demo": True,
        }

    if investor_id and investor_id not in set(store.investors["investor_id"].astype(str)):
        return {
            "error": "Investor not found",
            "investor_id": investor_id,
            "evidence": insufficient("Copilot", ["valid investor_id"]),
            "follow_ups": [],
            "is_demo": True,
        }

    handler = handlers.get(intent) or handlers["summary"]
    result = handler()
    result["query"] = q
    result["intent"] = intent
    result["mapped_function"] = ALLOWED_FUNCTIONS.get(intent, intent)
    result["allowed_functions"] = list(ALLOWED_FUNCTIONS.keys())
    result["no_arbitrary_sql"] = True
    result["scenario_id"] = (scenario or {}).get("id")
    result["is_demo"] = True

    # Conversation continuity
    next_ctx = {
        "investor_id": result.get("investor_id") or investor_id or conversation.get("investor_id"),
        "intent": intent,
        "scenario_id": result.get("scenario_id"),
    }
    result["conversation_context"] = {k: v for k, v in next_ctx.items() if v}
    if "follow_ups" not in result:
        result["follow_ups"] = _default_follow_ups(intent, result.get("investor_id"))
    if "links" not in result:
        result["links"] = _default_links(result.get("investor_id"), intent)
    return result


# ---------- Handlers (validated services only) ----------


def _handle_priority(store: DataStore, investor_id: str | None, lower: str) -> dict[str, Any]:
    assert investor_id
    pri = score_investor(store, investor_id)
    factors = [f for f in (pri.get("factors") or []) if (f.get("points") or 0) > 0 or f.get("name") in {
        "suppress_reason",
        "blind_spot_overlooked",
    }]
    bullets = [f"{f['name']}: {f['detail']} ({f.get('points', 0)} pts)" for f in factors[:8]]
    if not bullets:
        bullets = [pri.get("priority_reason") or "Within configured thresholds"]

    title = f"{pri.get('display_name')} — {pri.get('priority')} (score {pri.get('score')})"
    summary = pri.get("priority_reason") or title
    if "arjun" in lower or investor_id == "DEMO-INV-002":
        suppress = next((f for f in pri.get("factors") or [] if f.get("name") == "suppress_reason"), None)
        if suppress:
            summary = (
                f"{pri.get('display_name')} is {pri.get('priority')} (score {pri.get('score')}). "
                f"{suppress.get('detail')} Severity is separate from AUM movement alone."
            )

    claims = [
        {
            "text": f"Priority {pri.get('priority')} with score {pri.get('score')}",
            "status": pri.get("confidence") or "Limited",
            "source": "score_investor",
        }
    ]
    for f in factors[:5]:
        claims.append(
            {
                "text": f["detail"],
                "status": "Verified" if (f.get("points") or 0) > 0 or f.get("name") == "suppress_reason" else "Limited",
                "source": f"factor:{f.get('name')}",
            }
        )

    return {
        "investor_id": investor_id,
        "result": pri,
        "citations": _citations(pri),
        "evidence": pri.get("evidence"),
        "answer": {
            "title": title,
            "summary": summary,
            "bullets": bullets,
            "claims": claims,
        },
        "follow_ups": [
            f"Show the detailed priority breakdown for {investor_id}",
            f"Prepare a meeting brief for {investor_id}",
            f"What evidence supports the goal deviation for {investor_id}?",
            "Find overlooked clients who may need a review.",
        ],
        "links": [
            {"label": "Client profile", "href": f"/clients/{investor_id}/overview"},
            {"label": "Attention Engine", "href": "/attention-engine"},
        ],
    }


def _handle_summary(store: DataStore, investor_id: str | None) -> dict[str, Any]:
    assert investor_id
    data = build_structured_summary(store, investor_id)
    parts = data.get("parts") or []
    bullets = [f"{p.get('title')}: {p.get('summary')}" for p in parts[:6]]
    return {
        "investor_id": investor_id,
        "result": data,
        "citations": _citations(data),
        "evidence": data.get("evidence")
        or envelope("Structured summary", confidence=ConfidenceLevel.LIMITED, evidence=[]),
        "answer": {
            "title": f"Client summary — {investor_id}",
            "summary": "Structured evidence-backed summary from validated analytics.",
            "bullets": bullets or ["No summary parts available."],
            "claims": [
                {
                    "text": p.get("summary"),
                    "status": (p.get("evidence") or {}).get("confidence") or "Limited",
                    "source": p.get("id") or "structured_summary",
                }
                for p in parts[:5]
            ],
        },
        "follow_ups": _default_follow_ups("summary", investor_id),
        "links": _default_links(investor_id, "summary"),
    }


def _handle_drift(store: DataStore, investor_id: str | None) -> dict[str, Any]:
    assert investor_id
    data = detect_drift(store, investor_id)
    alerts = data.get("alerts") or []
    bullets = [
        f"{a.get('title') or a.get('alert_type')}: {a.get('detail') or a.get('message') or ''}"
        for a in alerts[:8]
    ]
    return {
        "investor_id": investor_id,
        "result": data,
        "citations": _citations(data),
        "evidence": data.get("evidence"),
        "answer": {
            "title": f"Drift / allocation signals — {investor_id}",
            "summary": f"{len(alerts)} drift alert(s) from validated drift detector.",
            "bullets": bullets or ["No material drift alerts on record."],
            "claims": [
                {
                    "text": b,
                    "status": (data.get("evidence") or {}).get("confidence") or "Limited",
                    "source": "detect_drift",
                }
                for b in bullets[:5]
            ],
        },
        "follow_ups": [
            f"Prepare a meeting brief for {investor_id}",
            f"What information is missing to assess {investor_id}'s financial position?",
            f"Why is {investor_id} prioritized now?",
        ],
        "links": _default_links(investor_id, "drift"),
    }


def _handle_advice(store: DataStore, investor_id: str | None) -> dict[str, Any]:
    assert investor_id
    data = advice_outcome_report(store, investor_id)
    items = data.get("items") or []
    bullets = [
        f"{i.get('advice_id') or 'advice'}: {i.get('outcome_status')} — {i.get('recommendation') or i.get('summary') or ''}"
        for i in items[:8]
    ]
    return {
        "investor_id": investor_id,
        "result": data,
        "citations": _citations(data),
        "evidence": (data.get("summary") if isinstance(data.get("summary"), dict) else None)
        or data.get("evidence"),
        "answer": {
            "title": f"Advice outcomes — {investor_id}",
            "summary": (
                f"{data.get('counts', {}).get('total', len(items))} advice item(s); "
                f"{data.get('counts', {}).get('insufficient_data', 0)} with insufficient outcome data."
            ),
            "bullets": bullets or ["No advice history on file."],
            "claims": [
                {
                    "text": f"{i.get('outcome_status')}: {i.get('recommendation') or i.get('summary')}",
                    "status": "Insufficient"
                    if i.get("outcome_status") == "Insufficient data"
                    else "Limited",
                    "source": "advice_outcome_report",
                }
                for i in items[:5]
            ],
        },
        "follow_ups": [
            f"Can you conclusively determine whether {investor_id}'s earlier recommendation succeeded?",
            f"Which follow-up actions are still outstanding for {investor_id}?",
            f"Prepare a meeting brief for {investor_id}",
        ],
        "links": _default_links(investor_id, "advice_outcome"),
    }


def _handle_insufficient_outcome(store: DataStore, investor_id: str | None) -> dict[str, Any]:
    """Demo: show honest insufficient-data stance using real advice-outcome engine."""
    assert investor_id
    # Prefer a client with insufficient items; fall back to requested client
    candidates = [investor_id, "DEMO-INV-001", "DEMO-INV-002"]
    chosen = investor_id
    data = advice_outcome_report(store, investor_id)
    insuff_items = [i for i in (data.get("items") or []) if i.get("outcome_status") == "Insufficient data"]
    if not insuff_items:
        for cid in candidates:
            if cid == investor_id:
                continue
            if not _accessible(cid):
                continue
            alt = advice_outcome_report(store, cid)
            alt_insuff = [i for i in (alt.get("items") or []) if i.get("outcome_status") == "Insufficient data"]
            if alt_insuff:
                chosen, data, insuff_items = cid, alt, alt_insuff
                break

    if insuff_items:
        item = insuff_items[0]
        ev = item.get("evidence") or {}
        missing = ev.get("missing_data") or item.get("missing_inputs") or ["outcome observation window"]
        if isinstance(missing, str):
            missing = [missing]
        bullets = [
            f"Investigating: {item.get('recommendation') or item.get('summary') or item.get('advice_id')}",
            f"Outcome status: {item.get('outcome_status')}",
            f"Available: advice date / recommendation text on record",
            f"Missing: {', '.join(str(m) for m in missing) if missing else 'required outcome inputs'}",
            "A reliable success/failure conclusion cannot be made until those inputs are verified.",
        ]
        summary = (
            "Insufficient data — Copilot will not invent an advice outcome. "
            "Retrieve the missing records before claiming success or failure."
        )
        conf = "Insufficient"
    else:
        bullets = [
            "No advice item currently marked Insufficient data for this client.",
            "Available items were evaluated; see advice outcome counts.",
            "If you expected an insufficient case, pick another client or record missing outcome inputs.",
        ]
        summary = (
            f"Evaluated {data.get('counts', {}).get('total', 0)} advice item(s); "
            "none are currently Insufficient data for a forced inconclusive demo."
        )
        conf = (data.get("summary") or {}).get("confidence") if isinstance(data.get("summary"), dict) else "Limited"

    return {
        "investor_id": chosen,
        "result": data,
        "citations": _citations(data),
        "evidence": envelope(
            summary,
            confidence=ConfidenceLevel.INSUFFICIENT if conf == "Insufficient" else ConfidenceLevel.LIMITED,
            evidence=[{"source": "advice_outcome_report", "record_ids": [chosen]}],
            missing_data=["post-advice outcome observations"] if insuff_items else [],
            limitations=["Do not treat silence as proof the recommendation failed or succeeded."],
            next_steps=["Verify holdings/returns after advice date", "Confirm client implementation"],
        ),
        "answer": {
            "title": "Can we conclude the recommendation succeeded?",
            "summary": summary,
            "bullets": bullets,
            "claims": [
                {
                    "text": b,
                    "status": conf if i == 0 else "Limited",
                    "source": "advice_outcome_report",
                }
                for i, b in enumerate(bullets)
            ],
        },
        "follow_ups": [
            f"What outcome was expected from previous advice for {chosen}?",
            f"Prepare a meeting brief for {chosen}",
            "Which clients have unresolved recommendations or overdue commitments?",
        ],
        "links": _default_links(chosen, "insufficient_outcome"),
    }


def _handle_whatif(store: DataStore, investor_id: str | None, lower: str) -> dict[str, Any]:
    assert investor_id
    data = simulate(
        store,
        investor_id,
        sip_delta=_parse_sip_delta(lower),
        return_delta_pp=_parse_return_delta(lower),
    )
    base = data.get("baseline") or {}
    alt = data.get("alternative") or {}
    bullets = [
        f"Scenario: {data.get('label') or data.get('scenario_type') or 'hypothetical'}",
        f"Baseline projected value: {base.get('projected_value')}",
        f"Alternative projected value: {alt.get('projected_value')}",
        f"Delta vs baseline: {data.get('delta_vs_baseline')}",
        f"Formula: {data.get('formula')}",
        "HYPOTHETICAL — not a return guarantee and not an investment recommendation.",
    ]
    for a in (data.get("assumptions") or [])[:4]:
        bullets.append(f"Assumption: {a}")
    data = {**data, "is_hypothetical": True}
    return {
        "investor_id": investor_id,
        "result": data,
        "citations": _citations(data),
        "evidence": data.get("evidence"),
        "answer": {
            "title": f"Hypothetical contribution scenario — {investor_id}",
            "summary": "What-if output from the validated simulator (hypothetical).",
            "bullets": [str(b) for b in bullets if b is not None],
            "claims": [
                {
                    "text": "Hypothetical projection — not guaranteed returns",
                    "status": "Limited",
                    "source": "simulate",
                }
            ],
        },
        "follow_ups": [
            f"Prepare a meeting brief for {investor_id}",
            f"Why is {investor_id} marked {score_investor(store, investor_id).get('priority')}?",
            "Open Market Shock Simulator",
        ],
        "links": [
            {"label": "Market Shock Simulator", "href": f"/what-if/{investor_id}"},
            {"label": "Client profile", "href": f"/clients/{investor_id}/overview"},
        ],
    }


def _handle_patterns(store: DataStore) -> dict[str, Any]:
    data = discover_patterns(store)
    cohorts = data.get("cohorts") or data.get("patterns") or []
    bullets = []
    for c in cohorts[:8]:
        bullets.append(
            f"{c.get('name') or c.get('cohort_id')}: {c.get('rule') or c.get('definition') or ''} "
            f"(n={c.get('count') or c.get('client_count') or len(c.get('investor_ids') or [])})"
        )
    return {
        "investor_id": None,
        "result": data,
        "citations": _citations(data),
        "evidence": data.get("evidence"),
        "answer": {
            "title": "Cross-client patterns (attention book)",
            "summary": "Patterns from discover_patterns — only cohorts the service actually identifies.",
            "bullets": bullets or ["No pattern cohorts returned by the service."],
            "claims": [
                {
                    "text": b,
                    "status": (data.get("evidence") or {}).get("confidence") or "Limited",
                    "source": "discover_patterns",
                }
                for b in bullets[:5]
            ],
        },
        "follow_ups": [
            "Who needs attention today?",
            "Find overlooked clients who may need a review.",
            "Which clients are falling behind their financial goals, and why?",
        ],
        "links": [
            {"label": "Insights", "href": "/insights"},
            {"label": "Attention Engine", "href": "/attention-engine"},
        ],
    }


def _handle_goal(store: DataStore, investor_id: str | None) -> dict[str, Any]:
    assert investor_id
    snap = investor_snapshot(store, investor_id)
    if snap.get("error"):
        return {
            "investor_id": investor_id,
            "error": snap["error"],
            "evidence": insufficient("Goal", ["goal"]),
            "answer": {
                "title": "Goal unavailable",
                "summary": snap["error"],
                "bullets": [],
                "claims": [],
            },
            "follow_ups": [],
            "links": _default_links(investor_id, "goal"),
        }
    gp = snap["goal_progress"]
    bullets = [
        f"Goal: {gp.get('goal_name')}",
        f"Deviation vs expected path: {gp.get('deviation_pct_vs_expected')}%",
        f"Progress to target: {gp.get('progress_to_target_pct')}%",
        f"Years remaining: {gp.get('years_remaining')}",
        f"Methodology: {gp.get('methodology')}",
    ]
    return {
        "investor_id": investor_id,
        "result": {"goal_progress": gp, "is_demo": True},
        "citations": ["synthetic_goals.csv", investor_id],
        "evidence": envelope(
            f"{gp['goal_name']}: {gp['deviation_pct_vs_expected']:+.1f}% vs expected",
            confidence=ConfidenceLevel.VERIFIED,
            evidence=[{"source": "synthetic_goals.csv", "detail": gp.get("methodology")}],
        ),
        "answer": {
            "title": f"Goal path — {snap['investor']['display_name']}",
            "summary": f"{gp['goal_name']} is {gp['deviation_pct_vs_expected']:+.1f}% vs expected path.",
            "bullets": bullets,
            "claims": [
                {
                    "text": f"Deviation {gp['deviation_pct_vs_expected']}% vs expected",
                    "status": "Verified",
                    "source": "goal_progress",
                }
            ],
        },
        "follow_ups": _default_follow_ups("goal", investor_id),
        "links": _default_links(investor_id, "goal"),
    }


def _handle_attention_book(store: DataStore) -> dict[str, Any]:
    ranked = [r for r in rank_book(store, include_resolved=False) if r["priority"] in {"Critical", "High"}]
    bullets = [
        f"{r['display_name']} ({r['investor_id']}): {r['priority']} score {r['score']} — {r.get('priority_reason')}"
        for r in ranked[:12]
    ]
    return {
        "investor_id": None,
        "result": {"clients": ranked[:25], "count": len(ranked)},
        "citations": ["rank_book"],
        "evidence": envelope(
            f"{len(ranked)} clients require review (Critical/High)",
            confidence=ConfidenceLevel.VERIFIED,
            evidence=[{"source": "rank_book", "detail": "unresolved Critical/High"}],
        ),
        "answer": {
            "title": "Who needs attention today?",
            "summary": f"{len(ranked)} unresolved Critical/High clients from the Attention Engine.",
            "bullets": bullets or ["No Critical/High clients in the active queue."],
            "claims": [
                {
                    "text": f"{len(ranked)} clients in Critical/High",
                    "status": "Verified",
                    "source": "rank_book",
                }
            ],
        },
        "follow_ups": [
            "Why is DEMO-INV-001 marked Critical?",
            "Find overlooked clients who may need a review.",
            "Which clients have overdue follow-ups?",
        ],
        "links": [{"label": "Attention Engine", "href": "/attention-engine"}],
    }


def _handle_less_observed(store: DataStore) -> dict[str, Any]:
    page = attention_engine_page.build_attention_engine(store)
    less = [
        c
        for c in (page.get("less_observed_clients") or [])
        if not c.get("resolved") and c.get("priority") in {"Critical", "High", "Monitor"}
    ][:15]
    # Prefer higher attention need first (already sorted)
    bullets = []
    for c in less[:10]:
        why = (c.get("why_now") or [c.get("main_reason")])[:2]
        bullets.append(
            f"{c['display_name']} ({c['investor_id']}): {c['priority']} score {c['score']} — "
            f"{'; '.join(why)}; {c.get('less_observed_reason') or 'less-observed segment'}"
        )
    hero = page.get("hero")
    summary = (
        f"{len(page.get('less_observed_clients') or [])} less-observed clients "
        f"(threshold {page.get('less_observed_definition', {}).get('stale_review_threshold_days')} days). "
        "Review-history evidence is separate from financial-risk score."
    )
    if hero:
        summary += f" DEMO overlooked case near top: {hero.get('display_name')} ({hero.get('investor_id')})."
    return {
        "investor_id": (hero or {}).get("investor_id"),
        "result": {
            "clients": less,
            "definition": page.get("less_observed_definition"),
            "hero": hero,
        },
        "citations": ["attention_engine_page", "blind_spot.review_obscurity"],
        "evidence": page.get("evidence"),
        "answer": {
            "title": "Overlooked / less-observed clients needing attention",
            "summary": summary,
            "bullets": bullets or ["No less-observed clients matched the current filters."],
            "claims": [
                {
                    "text": "Less-observed uses recorded last_review_date / overdue advice / note counts",
                    "status": "Verified",
                    "source": "blind_spot.review_obscurity",
                }
            ],
        },
        "follow_ups": [
            f"Why is {(hero or {}).get('investor_id') or 'DEMO-INV-L017'} prioritized?",
            "Who needs attention today?",
            "Prepare a meeting brief for DEMO-INV-L017",
        ],
        "links": [
            {"label": "Attention Engine (Less-Observed)", "href": "/attention-engine"},
            {
                "label": f"Profile {(hero or {}).get('display_name') or 'hero'}",
                "href": f"/clients/{(hero or {}).get('investor_id') or 'DEMO-INV-L017'}/overview",
            },
        ],
    }


def _handle_goal_behind(store: DataStore) -> dict[str, Any]:
    ranked = rank_book(store, include_resolved=False)
    behind = [
        r
        for r in ranked
        if (r.get("goal_status") or {}).get("deviation_pct_vs_expected", 0) <= -5
    ]
    behind.sort(key=lambda r: (r.get("goal_status") or {}).get("deviation_pct_vs_expected", 0))
    bullets = []
    for r in behind[:12]:
        gs = r.get("goal_status") or {}
        bullets.append(
            f"{r['display_name']} ({r['investor_id']}): {gs.get('goal_name')} "
            f"deviation {gs.get('deviation_pct_vs_expected')}% · priority {r['priority']} · "
            f"confidence {r.get('confidence')}"
        )
    return {
        "investor_id": None,
        "result": {"clients": behind[:25], "count": len(behind)},
        "citations": ["rank_book", "goal_progress"],
        "evidence": envelope(
            f"{len(behind)} clients ≤ -5% vs expected goal path",
            confidence=ConfidenceLevel.VERIFIED,
            evidence=[{"source": "rank_book+goal_progress"}],
        ),
        "answer": {
            "title": "Clients behind expected goal trajectory",
            "summary": f"{len(behind)} clients with deviation ≤ -5% vs expected path (DEMO).",
            "bullets": bullets or ["No clients currently meet the behind-goal threshold."],
            "claims": [
                {
                    "text": f"{len(behind)} clients behind expected path (≤ -5%)",
                    "status": "Verified",
                    "source": "goal_progress",
                }
            ],
        },
        "follow_ups": [
            "Why is DEMO-INV-001 marked Critical?",
            "Which findings are supported by verified data for DEMO-INV-001?",
            "Prepare a meeting brief for DEMO-INV-001",
        ],
        "links": [{"label": "Attention Engine", "href": "/attention-engine"}],
    }


def _handle_unresolved(store: DataStore) -> dict[str, Any]:
    ranked = rank_book(store, include_resolved=True)
    rows = []
    for r in ranked:
        advice = store.advice[store.advice["investor_id"] == r["investor_id"]]
        overdue = advice[advice["follow_up_status"] == "overdue"] if not advice.empty else advice
        commits = [
            c
            for c in load_commitments()
            if c.get("investor_id") == r["investor_id"]
            and c.get("status") in {"open", "pending", "confirmed"}
        ]
        if len(overdue) or commits:
            rows.append(
                {
                    **r,
                    "overdue_advice": int(len(overdue)),
                    "open_commitments": len(commits),
                }
            )
    rows.sort(key=lambda x: (-x["overdue_advice"], -x["open_commitments"], -x["score"]))
    bullets = [
        f"{r['display_name']} ({r['investor_id']}): {r['overdue_advice']} overdue advice, "
        f"{r['open_commitments']} open commitments — priority {r['priority']}"
        for r in rows[:12]
    ]
    return {
        "investor_id": None,
        "result": {"clients": rows[:25], "count": len(rows)},
        "citations": ["synthetic_advice.csv", "commitments"],
        "evidence": envelope(
            f"{len(rows)} clients with overdue advice and/or open commitments",
            confidence=ConfidenceLevel.VERIFIED,
            evidence=[{"source": "advice+commitments"}],
            limitations=[
                "Overdue advisor follow-up ≠ proof the investment recommendation failed.",
            ],
        ),
        "answer": {
            "title": "Unresolved recommendations & commitments",
            "summary": (
                f"{len(rows)} clients with overdue advice follow-ups and/or open commitments. "
                "These are process follow-ups, not automatic investment-failure verdicts."
            ),
            "bullets": bullets or ["No overdue advice or open commitments found."],
            "claims": [
                {
                    "text": "Overdue follow-up is distinct from unsuccessful advice outcome",
                    "status": "Verified",
                    "source": "advice follow_up_status",
                }
            ],
        },
        "follow_ups": [
            "Can you conclusively determine whether DEMO-INV-001's earlier recommendation succeeded?",
            "Who needs attention today?",
            "Prepare a meeting brief for DEMO-INV-001",
        ],
        "links": [{"label": "Attention Engine", "href": "/attention-engine"}],
    }


def _handle_meeting_prep(store: DataStore, investor_id: str | None) -> dict[str, Any]:
    assert investor_id
    data = pre_meeting_pack(store, investor_id)
    if data.get("error"):
        return {
            "investor_id": investor_id,
            "error": data["error"],
            "evidence": insufficient("Meeting prep", ["investor"]),
            "answer": {
                "title": "Meeting prep unavailable",
                "summary": data["error"],
                "bullets": [],
                "claims": [],
            },
            "follow_ups": [],
            "links": _default_links(investor_id, "meeting_prep"),
        }
    pri = data.get("priority") or {}
    agenda = data.get("agenda") or []
    commits = data.get("open_commitments") or []
    bullets = [
        f"Priority: {pri.get('priority')} (score {pri.get('score')}) — {pri.get('priority_reason')}",
        f"Open commitments: {len(commits)}",
        *[f"Agenda: {a}" for a in agenda[:5]],
        *[f"Highlight: {h.get('title')} — {h.get('summary')}" for h in (data.get("structured_highlights") or [])[:4]],
        "No meeting is claimed as scheduled unless a Meeting Intelligence record exists.",
    ]
    return {
        "investor_id": investor_id,
        "result": data,
        "citations": _citations(data),
        "evidence": data.get("evidence"),
        "answer": {
            "title": f"Meeting brief — {data.get('display_name')}",
            "summary": "Pre-meeting pack from validated analytics (not invented meeting notes).",
            "bullets": bullets,
            "claims": [
                {
                    "text": f"Priority {pri.get('priority')}",
                    "status": pri.get("confidence") or "Limited",
                    "source": "score_investor",
                }
            ],
        },
        "follow_ups": [
            f"Which follow-up actions are still outstanding for {investor_id}?",
            f"Summarize previous advice for {investor_id}",
            f"What information is missing to assess {investor_id}'s financial position?",
        ],
        "links": [
            {"label": "Client profile", "href": f"/clients/{investor_id}/overview"},
            {"label": "Meeting Intelligence", "href": f"/meeting-intel/{investor_id}/history"},
            {"label": "Meetings & Memory", "href": f"/meetings/{investor_id}"},
        ],
    }


def _handle_data_quality() -> dict[str, Any]:
    exceptions = txn_quality.list_exceptions()
    # If empty, run demo dirty validation to surface real DQ findings for the demo
    if not exceptions:
        try:
            from pathlib import Path

            demo = Path(__file__).resolve().parents[2] / "data" / "transactions" / "demo_dirty.csv"
            if demo.exists():
                txn_quality.validate_path(demo)
                exceptions = txn_quality.list_exceptions()
        except Exception:
            pass
    bullets = [
        f"{e.get('issue_type') or e.get('type')}: {e.get('detail') or e.get('message')} "
        f"(severity {e.get('severity') or 'n/a'})"
        for e in (exceptions or [])[:12]
    ]
    return {
        "investor_id": None,
        "result": {"exceptions": (exceptions or [])[:30], "count": len(exceptions or [])},
        "citations": ["txn_quality"],
        "evidence": envelope(
            f"{len(exceptions or [])} transaction data-quality exception(s)",
            confidence=ConfidenceLevel.VERIFIED if exceptions else ConfidenceLevel.LIMITED,
            evidence=[{"source": "txn_quality.list_exceptions"}],
            limitations=[
                "DQ issues do not automatically imply investment underperformance unless lineage supports it.",
            ],
        ),
        "answer": {
            "title": "Data-quality issues that can affect analysis",
            "summary": (
                f"{len(exceptions or [])} exception(s) from transaction validation. "
                "These affect cash-flow/ingestion reliability — not auto-classified as return failure."
            ),
            "bullets": bullets
            or [
                "No persisted exceptions yet — upload/validate a CSV or use the demo dirty file from Settings/Transactions tools.",
            ],
            "claims": [
                {
                    "text": "Transaction DQ ≠ portfolio return conclusion without lineage",
                    "status": "Verified",
                    "source": "txn_quality",
                }
            ],
        },
        "follow_ups": [
            "Who needs attention today?",
            "What information is missing to assess DEMO-INV-001's financial position?",
        ],
        "links": [{"label": "Insights / DQ tools", "href": "/insights"}],
    }


# ---------- Intent mapping & helpers ----------


def _map_intent(lower: str) -> str:
    if any(
        w in lower
        for w in (
            "overlook",
            "less-observed",
            "less observed",
            "frequently reviewed",
            "outside the frequently",
            "blind spot",
            "long-tail",
            "long tail",
        )
    ):
        return "less_observed"
    if any(w in lower for w in ("who needs attention", "needs attention today", "attention today", "attention queue")):
        return "attention_book"
    if any(w in lower for w in ("falling behind", "behind their", "goal trajectory", "expected goal", "behind goal")):
        return "goal_behind_book"
    if any(
        w in lower
        for w in (
            "unresolved recommendation",
            "overdue commitment",
            "overdue follow-up",
            "overdue followups",
            "unresolved advice",
            "revisit an earlier",
        )
    ):
        return "unresolved_book"
    if any(w in lower for w in ("prepare me", "meeting brief", "prepare a meeting", "next meeting", "discuss in the next")):
        return "meeting_prep"
    if any(w in lower for w in ("data-quality", "data quality", "duplicate transaction", "ingestion")):
        return "data_quality"
    if any(w in lower for w in ("conclusively", "insufficient data", "cannot determine", "succeeded?")):
        return "insufficient_outcome"
    if any(w in lower for w in ("pattern", "cohort", "across client", "book-wide", "book wide", "common patterns")):
        return "patterns"
    if any(w in lower for w in ("what if", "what-if", "simulate", "hypothetical", "increase their monthly", "increase sip", "contribution")):
        return "whatif"
    if any(w in lower for w in ("drift", "allocation deviation", "allocation drift", "hidden")):
        return "drift"
    if any(w in lower for w in ("advice outcome", "previous advice", "outcome was expected", "did the advice")):
        return "advice_outcome"
    if any(
        w in lower
        for w in (
            "priority",
            "attention score",
            "why critical",
            "marked critical",
            "critical?",
            "escalat",
            "why wasn't",
            "why wasnt",
            "priority score",
            "main reasons behind",
        )
    ):
        return "priority"
    if any(w in lower for w in ("goal", "expected path", "portfolio path", "performance analysis")):
        return "goal"
    if any(w in lower for w in ("missing", "insufficient", "what information")):
        return "summary"
    if any(w in lower for w in ("summary", "overview", "how is", "status", "notes and commitments")):
        return "summary"
    return "summary"


def _default_follow_ups(intent: str, investor_id: str | None) -> list[str]:
    iid = investor_id or "DEMO-INV-001"
    table = {
        "priority": [
            f"Show the detailed priority breakdown for {iid}",
            f"Prepare a meeting brief for {iid}",
            "Find overlooked clients who may need a review.",
        ],
        "meeting_prep": [
            f"Which follow-up actions are still outstanding for {iid}?",
            f"Summarize previous advice for {iid}",
            f"What would happen if {iid} increased SIP by 10000?",
        ],
        "less_observed": [
            "Why is DEMO-INV-L017 prioritized?",
            "Who needs attention today?",
            "Prepare a meeting brief for DEMO-INV-L017",
        ],
        "whatif": [
            f"Prepare a meeting brief for {iid}",
            f"Why is {iid} prioritized now?",
        ],
    }
    return table.get(
        intent,
        [
            f"Prepare a meeting brief for {iid}",
            "Who needs attention today?",
            "Find overlooked clients who may need a review.",
        ],
    )


def _default_links(investor_id: str | None, intent: str) -> list[dict[str, str]]:
    links = [{"label": "Attention Engine", "href": "/attention-engine"}]
    if investor_id:
        links.insert(0, {"label": "Client profile", "href": f"/clients/{investor_id}/overview"})
        if intent == "meeting_prep":
            links.append({"label": "Meeting Intelligence", "href": f"/meeting-intel/{investor_id}/history"})
        if intent == "whatif":
            links.append({"label": "Market Shock Simulator", "href": f"/what-if/{investor_id}"})
    return links


def _citations(data: dict[str, Any]) -> list[str]:
    cites: list[str] = []
    ev = data.get("evidence") or {}
    if isinstance(ev, dict):
        for item in ev.get("evidence") or []:
            src = item.get("source")
            if src:
                cites.append(src)
            for rid in item.get("record_ids") or []:
                cites.append(str(rid))
    return list(dict.fromkeys(cites))[:20]


def _parse_sip_delta(lower: str) -> float:
    m = re.search(r"(?:increase|raise|add)\s+(?:their\s+)?(?:monthly\s+)?(?:sip|contribution)\s+(?:by\s+)?(\d[\d,]*)", lower)
    if m:
        return float(m.group(1).replace(",", ""))
    m = re.search(r"sip\s+(?:by\s+)?(\d[\d,]*)", lower)
    if m:
        return float(m.group(1).replace(",", ""))
    m = re.search(r"sip\s*\+\s*(\d[\d,]*)", lower)
    if m:
        return float(m.group(1).replace(",", ""))
    return 10000.0 if "sip" in lower or "contribution" in lower else 0.0


def _parse_return_delta(lower: str) -> float:
    m = re.search(r"(?:return|expected)\s+(?:by\s+)?([+-]?\d+(?:\.\d+)?)\s*%?", lower)
    if m and "sip" not in lower[max(0, m.start() - 10) : m.start()]:
        return float(m.group(1))
    return 0.0
