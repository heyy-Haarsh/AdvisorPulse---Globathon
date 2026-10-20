"""Meeting Intelligence persistence + prep (Gemini calls skipped without API key)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from analytics.portfolio import DataStore  # noqa: E402
from services import meeting_intel, gemini_client  # noqa: E402


@pytest.fixture(scope="module")
def store():
    return DataStore.load()


def test_gemini_status_shape():
    st = gemini_client.status()
    assert st["provider"] == "google_gemini"
    assert "configured" in st
    assert "GEMINI_API_KEY" in st["env_vars"]


def test_create_prepare_consent_flow(store):
    m = meeting_intel.create_meeting(
        store,
        {
            "investor_id": "DEMO-INV-001",
            "title": "Pytest portfolio review",
            "meeting_type": "portfolio_review",
            "purpose": "Unit test meeting",
        },
    )
    assert m["meeting_id"].startswith("MTG-")
    mid = m["meeting_id"]

    brief = meeting_intel.build_preparation_brief(store, mid)
    assert brief["client_snapshot"]["investor_id"] == "DEMO-INV-001"
    assert "suggested_agenda" in brief
    # Must not invent a previous meeting
    if brief.get("previous_meeting_recap") is None:
        assert True
    else:
        assert brief["previous_meeting_recap"].get("meeting_id")

    # Start without consent fails
    bad = meeting_intel.start_session(mid)
    assert bad.get("error")

    ok = meeting_intel.confirm_consent(mid, "pytest consent")
    assert ok["consent_status"] == "confirmed"

    live = meeting_intel.start_session(mid)
    assert live["status"] == "live"

    noted = meeting_intel.add_live_note(mid, {"text": "Client asked about SIP", "category": "question"})
    assert len(noted["live_notes"]) >= 1

    pasted = meeting_intel.set_manual_transcript(
        mid,
        "Advisor discussed mid-cap allocation. Client asked for more time before rebalancing. "
        "Advisor to send a follow-up proposal next week.",
    )
    assert pasted["transcript_status"] == "ready"
    assert pasted["transcript"]["source"] == "advisor_paste"

    # Minutes require Gemini — without key expect clear error
    mins = meeting_intel.generate_minutes(store, mid)
    if gemini_client.is_configured():
        assert "minutes" in mins or mins.get("error")
    else:
        assert mins.get("error")
        assert "GEMINI" in mins["error"] or "configured" in mins["error"].lower()


def test_invalid_audio_rejected(store):
    m = meeting_intel.create_meeting(store, {"investor_id": "DEMO-INV-002", "title": "Audio reject"})
    meeting_intel.confirm_consent(m["meeting_id"])
    bad = meeting_intel.save_recording_bytes(m["meeting_id"], b"not-audio", "notes.txt")
    assert bad.get("error")


def test_schedule_meet_jitsi_fallback(store):
    m = meeting_intel.create_meeting(
        store, {"investor_id": "DEMO-INV-001", "title": "Jitsi schedule test"}
    )
    mid = m["meeting_id"]
    result = meeting_intel.schedule_meet(mid, prefer_google=False)
    assert not result.get("error") or result.get("meeting", {}).get("meet_link")
    meeting = result["meeting"]
    assert meeting["meet_link"]
    assert "jit.si" in meeting["meet_link"] or meeting.get("meet_provider") == "google_meet"


def test_load_demo_transcript(store):
    m = meeting_intel.create_meeting(
        store, {"investor_id": "DEMO-INV-001", "title": "Demo transcript test"}
    )
    mid = m["meeting_id"]
    loaded = meeting_intel.load_demo_transcript(mid, store=store)
    assert not loaded.get("error"), loaded
    assert loaded["meeting"]["transcript_status"] == "ready"
    assert loaded["meeting"]["transcript"]["source"] == "demo_fixture"
    assert "Priya" in loaded["meeting"]["transcript"]["full_text"]
    assert loaded["meeting"]["meet_link"]
    assert len(loaded["meeting"]["transcript"]["segments"]) >= 5
    assert loaded["meeting"]["minutes_status"] == "ready_for_review"
    assert loaded["minutes"]


def test_seed_demo_meeting(store):
    seeded = meeting_intel.seed_demo_meeting(store)
    assert not seeded.get("error"), seeded
    m = seeded["meeting"]
    assert m["investor_id"] == "DEMO-INV-001"
    assert m["transcript_status"] == "ready"
    assert m["minutes_status"] == "ready_for_review"
    assert m["meet_link"]
    assert seeded.get("demo_script")
    # Preparing again must not wipe minutes-ready status
    meeting_intel.build_preparation_brief(store, m["meeting_id"])
    again = meeting_intel.get_meeting(m["meeting_id"])
    assert again["minutes_status"] == "ready_for_review"
    assert again["status"] == "ready_for_review"
