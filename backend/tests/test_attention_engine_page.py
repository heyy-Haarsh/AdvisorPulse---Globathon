"""Dedicated Attention Engine page — reuses rank_book + blind_spot."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from analytics.portfolio import DataStore  # noqa: E402
from prioritization.engine import score_investor  # noqa: E402
from services import attention_engine_page, blind_spot  # noqa: E402
from services.blind_spot import BLIND_SPOT_HERO  # noqa: E402


@pytest.fixture(scope="module")
def store():
    return DataStore.load()


def test_attention_engine_payload_shape(store):
    payload = attention_engine_page.build_attention_engine(store)
    assert payload["is_demo"] is True
    assert payload.get("calculated_at")
    assert set(payload["kpis"]) >= {"critical", "high", "needs_review", "overdue_followups"}
    assert payload["counts"]["all"] == len(payload["clients"])
    assert payload["counts"]["less_observed"] == len(payload["less_observed_clients"])
    assert payload["less_observed_definition"]["stale_review_threshold_days"] >= 1
    assert all("segment" in c for c in payload["clients"])
    assert all("main_reason" in c for c in payload["clients"])


def test_kpis_match_client_records(store):
    payload = attention_engine_page.build_attention_engine(store)
    active = [c for c in payload["clients"] if not c.get("resolved")]
    assert payload["kpis"]["critical"] == sum(1 for c in active if c["priority"] == "Critical")
    assert payload["kpis"]["high"] == sum(1 for c in active if c["priority"] == "High")
    assert payload["kpis"]["needs_review"] == sum(1 for c in active if c.get("needs_review"))
    assert payload["kpis"]["overdue_followups"] == sum(
        1 for c in active if c.get("has_overdue_followup")
    )


def test_less_observed_uses_recorded_engagement(store):
    payload = attention_engine_page.build_attention_engine(store)
    for c in payload["less_observed_clients"]:
        assert c["segment"] == "less_observed"
        assert c.get("days_since_review") is not None
        assert c.get("obscurity_detail")
        # Must not invent neglect from notes alone — obscurity detail includes note_count
        assert "note_count" in c["obscurity_detail"]


def test_priya_critical_intact(store):
    pri = score_investor(store, "DEMO-INV-001")
    assert pri["priority"] == "Critical"
    assert pri["score"] >= 70
    payload = attention_engine_page.build_attention_engine(store)
    row = next(c for c in payload["clients"] if c["investor_id"] == "DEMO-INV-001")
    assert row["priority"] == "Critical"


def test_arjun_not_unjustified_critical(store):
    """DEMO-INV-002 planned withdrawal — must not be force-escalated to Critical."""
    pri = score_investor(store, "DEMO-INV-002")
    assert pri["priority"] != "Critical"
    assert any(f.get("name") == "suppress_reason" for f in pri["factors"])


def test_overlooked_hero_in_less_observed(store):
    payload = attention_engine_page.build_attention_engine(store)
    hero = payload["hero"]
    assert hero is not None
    assert hero["investor_id"] == BLIND_SPOT_HERO
    assert hero["segment"] == "less_observed"
    assert hero["is_blind_spot_hero"] is True
    assert hero["score"] >= 70 or hero["priority"] in {"Critical", "High"}
    assert any("blind" in (f.get("name") or "") or "overlook" in (f.get("detail") or "").lower()
               for f in hero.get("factors") or []) or hero.get("why_now")


def test_blind_spot_radar_still_works(store):
    radar = blind_spot.build_radar(store, segment="less_observed")
    assert radar["hero"]
    assert radar["hero"]["investor_id"] == BLIND_SPOT_HERO
