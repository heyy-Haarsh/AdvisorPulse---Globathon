"""Copilot demo scenarios — map to real services, not canned financial facts."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from analytics.portfolio import DataStore  # noqa: E402
from domain.persistence import load_settings, save_settings  # noqa: E402
from services import copilot, copilot_demo_library as demo_lib  # noqa: E402
from services.blind_spot import BLIND_SPOT_HERO  # noqa: E402


@pytest.fixture(scope="module")
def store():
    return DataStore.load()


def test_demo_catalog_shape():
    cat = demo_lib.catalog()
    assert len(cat["scenarios"]) >= 10
    assert "attention" in cat["quick_start"]
    assert cat["note"]


def test_seeded_scenarios_map_to_expected_intents(store):
    for s in demo_lib.SCENARIOS:
        r = copilot.route_query(store, s["question"])
        assert r.get("denied") is not True, s["id"]
        assert r["intent"] == s["expected_intent"], (s["id"], r["intent"])
        assert r["mapped_function"] == s["expected_function"], s["id"]
        assert r.get("no_arbitrary_sql") is True
        assert r.get("answer") and r["answer"].get("bullets") is not None


def test_critical_client_uses_live_score(store):
    r = copilot.route_query(store, "Why is DEMO-INV-001 marked Critical?")
    assert r["intent"] == "priority"
    pri = r["result"]
    assert pri["investor_id"] == "DEMO-INV-001"
    assert pri["priority"] == "Critical"
    assert pri["score"] >= 70
    # Answer must reflect live score, not a fixed template number alone
    assert str(pri["score"]) in r["answer"]["title"] or str(pri["score"]) in r["answer"]["summary"]


def test_overlooked_uses_attention_engine(store):
    r = copilot.route_query(
        store, "Which clients outside the frequently reviewed group need attention?"
    )
    assert r["intent"] == "less_observed"
    clients = r["result"]["clients"]
    assert clients
    hero = r["result"].get("hero")
    assert hero and hero["investor_id"] == BLIND_SPOT_HERO
    assert "less-observed" in r["answer"]["summary"].lower() or "overlook" in r["answer"]["title"].lower()


def test_arjun_not_unjustified_critical(store):
    r = copilot.route_query(
        store, "Why wasn't Arjun Mehta escalated even though his AUM declined?"
    )
    assert r["investor_id"] == "DEMO-INV-002"
    assert r["result"]["priority"] != "Critical"
    assert any(f.get("name") == "suppress_reason" for f in r["result"]["factors"])


def test_goal_behind_book(store):
    r = copilot.route_query(store, "Which clients are falling behind their financial goals, and why?")
    assert r["intent"] == "goal_behind_book"
    assert r["result"]["count"] >= len(r["result"]["clients"])
    assert r["result"]["clients"]
    for c in r["result"]["clients"][:5]:
        assert c["goal_status"]["deviation_pct_vs_expected"] <= -5


def test_insufficient_outcome_honest(store):
    r = copilot.route_query(
        store,
        "Can you conclusively determine whether this client's earlier recommendation succeeded?",
        context_investor_id="DEMO-INV-001",
    )
    assert r["intent"] == "insufficient_outcome"
    text = (r["answer"]["summary"] + " " + " ".join(r["answer"]["bullets"])).lower()
    assert "insufficient" in text or "cannot" in text or "none are currently" in text


def test_meeting_prep_no_fake_schedule(store):
    r = copilot.route_query(store, "Prepare me for my next meeting with DEMO-INV-001.")
    assert r["intent"] == "meeting_prep"
    assert r["investor_id"] == "DEMO-INV-001"
    joined = " ".join(r["answer"]["bullets"]).lower()
    assert "scheduled" not in joined or "no meeting is claimed" in " ".join(r["answer"]["bullets"]).lower()
    assert r["result"].get("agenda") is not None


def test_whatif_hypothetical(store):
    r = copilot.route_query(
        store,
        "What would happen to this goal if DEMO-INV-001 increased their monthly SIP by 10000?",
    )
    assert r["intent"] == "whatif"
    assert r["result"].get("is_hypothetical") is True or "HYPOTHETICAL" in " ".join(r["answer"]["bullets"])


def test_conversation_context_resolves_them(store):
    first = copilot.route_query(store, "Why is DEMO-INV-001 marked Critical?")
    ctx = first["conversation_context"]
    second = copilot.route_query(
        store,
        "Prepare me for a meeting with them.",
        conversation_context=ctx,
    )
    assert second["investor_id"] == "DEMO-INV-001"
    assert second["intent"] == "meeting_prep"


def test_access_control_on_followup(store):
    save_settings({"accessible_clients": ["DEMO-INV-001"]})
    try:
        denied = copilot.route_query(store, "summary for DEMO-INV-002")
        assert denied.get("denied") is True
        allowed = copilot.route_query(
            store,
            "Prepare me for a meeting with them.",
            conversation_context={"investor_id": "DEMO-INV-001"},
        )
        assert allowed.get("denied") is not True
        assert allowed["investor_id"] == "DEMO-INV-001"
    finally:
        save_settings({"accessible_clients": None})


def test_unresolved_and_patterns_and_dq(store):
    u = copilot.route_query(
        store, "Which clients have unresolved recommendations or overdue commitments?"
    )
    assert u["intent"] == "unresolved_book"
    p = copilot.route_query(
        store, "What common patterns are emerging across the clients who need attention?"
    )
    assert p["intent"] == "patterns"
    d = copilot.route_query(store, "Which data-quality issues could affect our financial analysis?")
    assert d["intent"] == "data_quality"
