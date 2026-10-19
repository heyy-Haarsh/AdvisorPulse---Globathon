"""
Private Advisor Memory (Feature 4).

Notes + mock/local transcription clearly labeled.
Structured extraction; advisor confirm before authoritative.
Links to Attention Engine follow-ups.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from domain.evidence import ConfidenceLevel, envelope
from domain.persistence import (
    load_extractions,
    load_notes_runtime,
    save_decision,
    save_extractions,
    save_notes_runtime,
    audit,
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def list_memory(investor_id: str | None, seed_notes: list[dict[str, Any]]) -> dict[str, Any]:
    runtime = load_notes_runtime()
    all_notes = list(seed_notes) + runtime
    if investor_id:
        all_notes = [n for n in all_notes if n.get("investor_id") == investor_id]
    extractions = load_extractions()
    if investor_id:
        extractions = [e for e in extractions if e.get("investor_id") == investor_id]
    return {
        "notes": all_notes,
        "extractions": extractions,
        "transcription_mode": "mocked_local",
        "transcription_disclaimer": (
            "MOCK / LOCAL path only — demo does not upload audio. "
            "Replace with on-device ASR (Whisper.cpp / Vosk) for production."
        ),
        "is_demo": True,
    }


def add_note(investor_id: str, note_text: str, author: str = "DEMO-ADV-USER-01") -> dict[str, Any]:
    notes = load_notes_runtime()
    note = {
        "note_id": f"DEMO-NOTE-RT-{uuid4().hex[:8]}",
        "investor_id": investor_id,
        "is_demo": "true",
        "created_at": _now(),
        "updated_at": _now(),
        "author": author,
        "note_text": note_text,
        "source": "manual",
        "transcript_local": "false",
        "authoritative": True,
    }
    notes.append(note)
    save_notes_runtime(notes)
    audit("note_create", {"investor_id": investor_id, "note_id": note["note_id"]})
    # Auto-extract candidates (not authoritative until confirm)
    extract_from_text(investor_id, note_text, note["note_id"], auto=True)
    return note


def mock_transcribe(
    investor_id: str,
    mock_transcript: str | None = None,
    audio_filename: str = "mock_meeting.wav",
) -> dict[str, Any]:
    text = mock_transcript or (
        "[MOCK LOCAL TRANSCRIPT] Client discussed goal timeline and comfort with equity volatility. "
        "Advisor to follow up on rebalancing by next month. Increase SIP discussed. "
        "DEMO ONLY — no real audio processed."
    )
    notes = load_notes_runtime()
    note = {
        "note_id": f"DEMO-NOTE-TX-{uuid4().hex[:8]}",
        "investor_id": investor_id,
        "is_demo": "true",
        "created_at": _now(),
        "updated_at": _now(),
        "author": "DEMO-ADV-USER-01",
        "note_text": text,
        "source": "mock_local_transcription",
        "transcript_local": "true",
        "audio_filename": audio_filename,
        "processing_mode": "mocked_local — replace with on-device ASR; no external model call in demo",
        "authoritative": False,
        "needs_confirmation": True,
    }
    notes.append(note)
    save_notes_runtime(notes)
    extraction = extract_from_text(investor_id, text, note["note_id"], auto=True)
    audit("mock_transcription", {"investor_id": investor_id, "note_id": note["note_id"]})
    return {
        "status": "ok",
        "processing_mode": "mocked_local",
        "note": note,
        "extraction": extraction,
        "security_note": "Production must keep audio/transcripts on approved infrastructure with consent.",
    }


def extract_from_text(
    investor_id: str,
    text: str,
    source_note_id: str,
    auto: bool = False,
) -> dict[str, Any]:
    """Rule-based structured extraction — candidates until advisor confirms."""
    lower = text.lower()
    commitments: list[str] = []
    topics: list[str] = []
    follow_ups: list[str] = []

    if "rebalanc" in lower:
        topics.append("rebalancing")
        commitments.append("Discuss / execute rebalancing")
    if "sip" in lower:
        topics.append("sip")
        commitments.append("Review SIP level")
    if "follow up" in lower or "follow-up" in lower:
        follow_ups.append("Advisor follow-up mentioned in note")
    if "goal" in lower or "timeline" in lower:
        topics.append("goal_timeline")
    if "risk" in lower or "volatil" in lower:
        topics.append("risk_tolerance")
    if "withdraw" in lower:
        topics.append("liquidity")

    due = None
    m = re.search(r"by (next month|next week|\d{4}-\d{2}-\d{2})", lower)
    if m:
        due = m.group(1)

    record = {
        "extraction_id": str(uuid4()),
        "investor_id": investor_id,
        "source_note_id": source_note_id,
        "created_at": _now(),
        "topics": topics,
        "commitments": commitments,
        "follow_ups": follow_ups,
        "suggested_due": due,
        "status": "pending_confirmation",
        "authoritative": False,
        "auto": auto,
        "evidence": envelope(
            "Structured extraction from note/transcript",
            confidence=ConfidenceLevel.LIMITED,
            evidence=[
                {
                    "source": "advisor_memory",
                    "record_ids": [source_note_id],
                    "detail": "Rule-based NLP; not authoritative until confirmed",
                }
            ],
            limitations=["Extraction is heuristic — advisor must confirm."],
            next_steps=["Confirm to create Attention follow-up / commitment."],
        ),
    }
    items = load_extractions()
    items.append(record)
    save_extractions(items)
    return record


def confirm_extraction(extraction_id: str, create_followup: bool = True) -> dict[str, Any]:
    items = load_extractions()
    for e in items:
        if e["extraction_id"] == extraction_id:
            e["status"] = "confirmed"
            e["authoritative"] = True
            e["confirmed_at"] = _now()
            save_extractions(items)
            followup = None
            if create_followup and (e.get("commitments") or e.get("follow_ups")):
                key = f"memory::{e['investor_id']}::{extraction_id}"
                followup = save_decision(
                    key,
                    {
                        "investor_id": e["investor_id"],
                        "action": "follow_up",
                        "source": "advisor_memory",
                        "extraction_id": extraction_id,
                        "detail": "; ".join(e.get("commitments") or e.get("follow_ups") or []),
                    },
                )
            audit("extraction_confirm", {"extraction_id": extraction_id, "investor_id": e["investor_id"]})
            return {"extraction": e, "attention_followup": followup}
    raise KeyError("extraction not found")


def dismiss_extraction(extraction_id: str) -> dict[str, Any]:
    items = load_extractions()
    for e in items:
        if e["extraction_id"] == extraction_id:
            e["status"] = "dismissed"
            e["authoritative"] = False
            save_extractions(items)
            return e
    raise KeyError("extraction not found")
