"""
Meeting Intelligence — prepare → record/upload → transcript → MoM → approve → commitments.

Persistence: data/runtime/meetings_intel.json
Recordings: data/runtime/recordings/ (not publicly served)
AI: Gemini via services.gemini_client (when GEMINI_API_KEY set)
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from analytics.portfolio import DataStore, investor_snapshot
from domain.evidence import ConfidenceLevel, envelope, insufficient
from domain.persistence import RUNTIME, _read, _write, audit, load_commitments, upsert_commitment
from prioritization.engine import score_investor
from services import gemini_client
from services.advice_outcome import advice_outcome_report
from services.drift import detect_drift
from services.meetings import pre_meeting_pack

MEETINGS_FILE = "meetings_intel.json"
RECORDINGS = RUNTIME / "recordings"
RECORDINGS.mkdir(parents=True, exist_ok=True)

ALLOWED_AUDIO = {".webm", ".wav", ".mp3", ".m4a", ".ogg", ".flac"}
MAX_AUDIO_BYTES = 25 * 1024 * 1024  # 25 MB


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load() -> list[dict[str, Any]]:
    return list(_read(MEETINGS_FILE, []))


def _save(items: list[dict[str, Any]]) -> None:
    _write(MEETINGS_FILE, items)


def _get(meeting_id: str) -> dict[str, Any] | None:
    for m in _load():
        if m.get("meeting_id") == meeting_id:
            return m
    return None


def _put(meeting: dict[str, Any]) -> dict[str, Any]:
    items = _load()
    found = False
    for i, m in enumerate(items):
        if m.get("meeting_id") == meeting["meeting_id"]:
            items[i] = meeting
            found = True
            break
    if not found:
        items.append(meeting)
    meeting["updated_at"] = _now()
    _save(items)
    return meeting


def provider_status() -> dict[str, Any]:
    return gemini_client.status()


def list_meetings(investor_id: str | None = None) -> dict[str, Any]:
    items = _load()
    if investor_id:
        items = [m for m in items if m.get("investor_id") == investor_id]
    items.sort(key=lambda m: m.get("scheduled_at") or m.get("created_at") or "", reverse=True)
    return {"meetings": items, "count": len(items), "gemini": provider_status(), "is_demo": True}


def get_meeting(meeting_id: str) -> dict[str, Any]:
    m = _get(meeting_id)
    if not m:
        return {"error": "Meeting not found", "meeting_id": meeting_id}
    return {**m, "gemini": provider_status(), "is_demo": True}


def create_meeting(store: DataStore, body: dict[str, Any]) -> dict[str, Any]:
    investor_id = str(body.get("investor_id") or "").strip()
    snap = investor_snapshot(store, investor_id)
    if snap.get("error"):
        return {"error": snap["error"]}

    meeting_id = f"MTG-{uuid4().hex[:10].upper()}"
    meeting = {
        "meeting_id": meeting_id,
        "investor_id": investor_id,
        "display_name": snap["investor"]["display_name"],
        "title": body.get("title") or f"Meeting with {snap['investor']['display_name']}",
        "meeting_type": body.get("meeting_type") or "portfolio_review",
        "scheduled_at": body.get("scheduled_at") or _now(),
        "expected_duration_min": body.get("expected_duration_min") or 45,
        "participants": body.get("participants")
        or ["DEMO-ADV-USER-01", snap["investor"]["display_name"]],
        "channel": body.get("channel") or "online",
        "purpose": body.get("purpose") or "",
        "advisor_prep_notes": body.get("advisor_prep_notes") or "",
        "agenda": body.get("agenda") or [],
        "custom_questions": body.get("custom_questions") or [],
        "checklist": _default_checklist(),
        "status": "prepared",
        "consent_status": "not_confirmed",
        "consent_confirmed_at": None,
        "consent_note": None,
        "recording_status": "ready",
        "recording_path": None,
        "recording_mime": None,
        "transcript_status": "none",
        "transcript": {"full_text": "", "segments": [], "source": None, "edited": False},
        "live_notes": [],
        "minutes_status": "none",
        "minutes": None,
        "minutes_version": 0,
        "approved_at": None,
        "approved_by": None,
        "started_at": None,
        "ended_at": None,
        "created_at": _now(),
        "updated_at": _now(),
        "is_demo": True,
    }
    _put(meeting)
    audit("meeting_intel_create", {"meeting_id": meeting_id, "investor_id": investor_id})
    return meeting


def _default_checklist() -> list[dict[str, Any]]:
    items = [
        "Review previous meeting notes",
        "Review outstanding commitments",
        "Check portfolio allocation",
        "Review goal progress",
        "Confirm the meeting agenda",
        "Identify missing client information",
    ]
    return [{"id": f"chk-{i}", "label": t, "done": False} for i, t in enumerate(items)]


def build_preparation_brief(store: DataStore, meeting_id: str, *, regenerate: bool = False) -> dict[str, Any]:
    meeting = _get(meeting_id)
    if not meeting:
        return {"error": "Meeting not found"}

    investor_id = meeting["investor_id"]
    pack = pre_meeting_pack(store, investor_id)
    if pack.get("error"):
        return pack

    snap = investor_snapshot(store, investor_id)
    pri = score_investor(store, investor_id)
    ao = advice_outcome_report(store, investor_id)
    drift = detect_drift(store, investor_id)
    commitments = [
        c
        for c in load_commitments()
        if c.get("investor_id") == investor_id and c.get("status") in {"open", "pending", "confirmed"}
    ]

    # Previous meetings from intel store only (never fabricate)
    prior = [
        m
        for m in _load()
        if m.get("investor_id") == investor_id
        and m.get("meeting_id") != meeting_id
        and m.get("minutes_status") in {"approved", "ready_for_review", "draft"}
    ]
    prior.sort(key=lambda m: m.get("ended_at") or m.get("scheduled_at") or "", reverse=True)
    prev = prior[0] if prior else None
    prev_recap = None
    if prev and prev.get("minutes"):
        mins = prev["minutes"]
        prev_recap = {
            "meeting_id": prev["meeting_id"],
            "date": prev.get("ended_at") or prev.get("scheduled_at"),
            "title": prev.get("title"),
            "executive_summary": mins.get("executive_summary") or [],
            "advice_items": mins.get("advice_items") or [],
            "decisions": mins.get("decisions") or [],
            "action_items": mins.get("action_items") or [],
            "unresolved_questions": mins.get("unresolved_questions") or [],
            "link": f"/meeting-intel/{investor_id}/history",
        }
    elif prev:
        prev_recap = {
            "meeting_id": prev["meeting_id"],
            "date": prev.get("scheduled_at"),
            "title": prev.get("title"),
            "note": "Prior meeting exists but approved minutes are not available.",
            "executive_summary": [],
        }

    pending_advice = [
        {
            "advice_id": i.get("advice_id"),
            "description": i.get("recommendation"),
            "date": i.get("advice_date"),
            "status": i.get("outcome_status"),
            "evidence_status": (i.get("evidence") or {}).get("confidence"),
            "suggested_question": f"Shall we revisit: {i.get('recommendation')}?",
        }
        for i in (ao.get("items") or [])
        if str(i.get("outcome_status") or "").lower()
        not in {"aligned", "completed", "resolved"}
    ][:8]

    changes = []
    gp = snap.get("goal_progress") or {}
    if gp.get("deviation_pct_vs_expected") is not None:
        changes.append(
            {
                "title": "Goal path deviation",
                "detail": f"{gp.get('goal_name')}: {gp.get('deviation_pct_vs_expected')}% vs expected path",
                "period": snap.get("data_timestamps", {}).get("as_of"),
                "kind": "actual",
            }
        )
    perf = snap.get("performance") or {}
    if perf.get("active_return_pct") is not None:
        changes.append(
            {
                "title": "Active return vs benchmark",
                "detail": f"{perf.get('active_return_pct')} pp (TWR window)",
                "period": perf.get("methodology", "")[:80],
                "kind": "actual",
            }
        )
    for a in (drift.get("alerts") or [])[:5]:
        changes.append(
            {
                "title": a.get("title"),
                "detail": (a.get("evidence") or {}).get("claim"),
                "period": None,
                "kind": "alert",
                "evidence_status": (a.get("evidence") or {}).get("confidence"),
            }
        )

    topics = []
    for f in (pri.get("factors") or [])[:5]:
        if f.get("points", 0) <= 0 and f.get("name") == "data_quality":
            continue
        topics.append(
            {
                "title": f.get("name"),
                "why_it_matters": f.get("detail"),
                "suggested_question": f"How should we address: {f.get('detail')}?",
                "priority": "high" if f.get("points", 0) >= 15 else "medium",
                "evidence_status": pri.get("confidence") or "Limited",
            }
        )

    agenda = meeting.get("agenda") or pack.get("agenda") or [
        "Review previous action items",
        "Discuss progress toward goals",
        "Review portfolio allocation and deviations",
        "Understand liquidity needs and changing circumstances",
        "Discuss possible actions",
        "Confirm decisions and follow-up responsibilities",
    ]
    questions = meeting.get("custom_questions") or (pack.get("brief") or {}).get("open_questions") or []

    brief: dict[str, Any] = {
        "meeting_id": meeting_id,
        "investor_id": investor_id,
        "client_snapshot": {
            "display_name": snap["investor"]["display_name"],
            "investor_id": investor_id,
            "city": snap["investor"].get("city"),
            "goal": gp.get("goal_name"),
            "portfolio_value": snap.get("portfolio_value"),
            "priority": pri.get("priority"),
            "score": pri.get("score"),
            "risk_profile": snap["investor"].get("risk_profile"),
            "last_review_date": snap["investor"].get("last_review_date"),
            "open_commitments_count": len(commitments),
        },
        "previous_meeting_recap": prev_recap,
        "portfolio_and_goal_changes": changes,
        "pending_advice": pending_advice,
        "pending_commitments": commitments,
        "priority_topics": topics[:5],
        "suggested_agenda": agenda,
        "questions_to_ask": questions[:8],
        "checklist": meeting.get("checklist") or _default_checklist(),
        "gemini_enrichment": None,
        "evidence": pack.get("evidence"),
        "limitations": [
            "Preparation uses DEMO analytics and recorded Meeting Intelligence history only.",
            "No previous meeting is invented when none exists.",
        ],
        "is_demo": True,
    }

    if gemini_client.is_configured() and (regenerate or not meeting.get("prep_brief_gemini")):
        try:
            enriched = gemini_client.generate_json(
                json.dumps(
                    {
                        "task": "Enrich advisor meeting preparation",
                        "meeting_purpose": meeting.get("purpose"),
                        "meeting_type": meeting.get("meeting_type"),
                        "client_snapshot": brief["client_snapshot"],
                        "changes": changes,
                        "pending_advice": pending_advice,
                        "topics": topics,
                        "schema": {
                            "priority_topics": [
                                {
                                    "title": "str",
                                    "why_it_matters": "str",
                                    "suggested_question": "str",
                                    "priority": "high|medium|low",
                                    "evidence_status": "Verified|Limited|Insufficient",
                                }
                            ],
                            "suggested_agenda": ["str"],
                            "questions_to_ask": ["str"],
                            "executive_prep_bullets": ["str"],
                        },
                        "rules": "Only use provided facts. Do not invent AUM, returns, or meetings.",
                    }
                )
            )
            brief["gemini_enrichment"] = enriched
            if enriched.get("priority_topics"):
                brief["priority_topics"] = enriched["priority_topics"][:5]
            if enriched.get("suggested_agenda"):
                brief["suggested_agenda"] = enriched["suggested_agenda"]
            if enriched.get("questions_to_ask"):
                brief["questions_to_ask"] = enriched["questions_to_ask"][:8]
            meeting["prep_brief_gemini"] = enriched
        except Exception as e:
            brief["gemini_enrichment_error"] = str(e)

    if not meeting.get("agenda"):
        meeting["agenda"] = list(brief["suggested_agenda"])
    meeting["prep_brief"] = {
        k: brief[k]
        for k in (
            "client_snapshot",
            "previous_meeting_recap",
            "portfolio_and_goal_changes",
            "pending_advice",
            "priority_topics",
            "questions_to_ask",
            "limitations",
        )
        if k in brief
    }
    meeting["status"] = "prepared"
    _put(meeting)
    return brief


def update_meeting(meeting_id: str, patch: dict[str, Any]) -> dict[str, Any]:
    meeting = _get(meeting_id)
    if not meeting:
        return {"error": "Meeting not found"}
    allowed = {
        "title",
        "meeting_type",
        "scheduled_at",
        "expected_duration_min",
        "participants",
        "channel",
        "purpose",
        "advisor_prep_notes",
        "agenda",
        "custom_questions",
        "checklist",
        "status",
    }
    for k, v in patch.items():
        if k in allowed:
            meeting[k] = v
    return _put(meeting)


def confirm_consent(meeting_id: str, note: str = "") -> dict[str, Any]:
    meeting = _get(meeting_id)
    if not meeting:
        return {"error": "Meeting not found"}
    meeting["consent_status"] = "confirmed"
    meeting["consent_confirmed_at"] = _now()
    meeting["consent_note"] = note or "Advisor confirmed participant consent obtained."
    audit("meeting_intel_consent", {"meeting_id": meeting_id})
    return _put(meeting)


def start_session(meeting_id: str) -> dict[str, Any]:
    meeting = _get(meeting_id)
    if not meeting:
        return {"error": "Meeting not found"}
    if meeting.get("consent_status") != "confirmed":
        return {"error": "Confirm recording consent before starting a live session"}
    if meeting.get("recording_status") == "recording":
        return {"error": "Recording already in progress", "meeting": meeting}
    meeting["status"] = "live"
    meeting["recording_status"] = "recording"
    meeting["started_at"] = meeting.get("started_at") or _now()
    return _put(meeting)


def set_recording_state(meeting_id: str, state: str) -> dict[str, Any]:
    meeting = _get(meeting_id)
    if not meeting:
        return {"error": "Meeting not found"}
    if state not in {"ready", "recording", "paused", "stopped", "uploading", "failed"}:
        return {"error": "Invalid recording state"}
    meeting["recording_status"] = state
    if state == "stopped":
        meeting["status"] = "transcribing" if meeting.get("recording_path") else "live"
    return _put(meeting)


def add_live_note(meeting_id: str, body: dict[str, Any]) -> dict[str, Any]:
    meeting = _get(meeting_id)
    if not meeting:
        return {"error": "Meeting not found"}
    note = {
        "note_id": f"LN-{uuid4().hex[:8]}",
        "category": body.get("category") or "general",
        "text": body.get("text") or "",
        "timestamp": body.get("timestamp") or _now(),
        "linked_segment_ids": body.get("linked_segment_ids") or [],
        "created_at": _now(),
    }
    meeting.setdefault("live_notes", []).append(note)
    return _put(meeting)


def save_recording_bytes(
    meeting_id: str,
    content: bytes,
    filename: str,
    mime_type: str | None = None,
) -> dict[str, Any]:
    meeting = _get(meeting_id)
    if not meeting:
        return {"error": "Meeting not found"}
    if meeting.get("consent_status") != "confirmed":
        return {"error": "Confirm consent before uploading/recording audio"}
    if len(content) > MAX_AUDIO_BYTES:
        return {"error": f"File exceeds {MAX_AUDIO_BYTES // (1024*1024)}MB limit"}
    ext = Path(filename).suffix.lower() or ".webm"
    if ext not in ALLOWED_AUDIO:
        return {"error": f"Unsupported audio type {ext}. Allowed: {sorted(ALLOWED_AUDIO)}"}

    dest = RECORDINGS / f"{meeting_id}{ext}"
    dest.write_bytes(content)
    meeting["recording_path"] = str(dest)
    meeting["recording_mime"] = mime_type or gemini_client._guess_mime(dest)
    meeting["recording_status"] = "stopped"
    meeting["recording_sha256"] = hashlib.sha256(content).hexdigest()
    meeting["transcript_status"] = "queued"
    audit("meeting_intel_recording_saved", {"meeting_id": meeting_id, "bytes": len(content)})
    return _put(meeting)


def set_manual_transcript(meeting_id: str, text: str, segments: list | None = None) -> dict[str, Any]:
    """Advisor-supplied transcript (not fabricated). Useful when Gemini audio fails."""
    meeting = _get(meeting_id)
    if not meeting:
        return {"error": "Meeting not found"}
    text = (text or "").strip()
    if not text:
        return {"error": "Transcript text is empty"}
    segs = segments or [
        {
            "segment_id": f"SEG-{uuid4().hex[:6]}",
            "start_time": "00:00",
            "end_time": "",
            "speaker_id": "Speaker 1",
            "text": text,
            "source_type": "advisor_paste",
        }
    ]
    for s in segs:
        s.setdefault("segment_id", f"SEG-{uuid4().hex[:6]}")
    meeting["transcript"] = {
        "full_text": text,
        "segments": segs,
        "source": "advisor_paste",
        "edited": False,
        "provider": None,
    }
    meeting["transcript_status"] = "ready"
    meeting["status"] = "transcript_ready"
    return _put(meeting)


def transcribe_meeting(meeting_id: str) -> dict[str, Any]:
    meeting = _get(meeting_id)
    if not meeting:
        return {"error": "Meeting not found"}
    path = meeting.get("recording_path")
    if not path or not Path(path).exists():
        return {
            "error": "No recording on file. Upload audio or paste an advisor-provided transcript.",
            "gemini": provider_status(),
        }
    if not gemini_client.is_configured():
        meeting["transcript_status"] = "failed"
        meeting["transcript_error"] = "GEMINI_API_KEY not configured"
        _put(meeting)
        return {
            "error": "GEMINI_API_KEY not configured",
            "gemini": provider_status(),
            "meeting": meeting,
        }

    meeting["transcript_status"] = "transcribing"
    meeting["status"] = "transcribing"
    _put(meeting)
    try:
        result = gemini_client.transcribe_audio_file(
            Path(path), mime_type=meeting.get("recording_mime")
        )
        segments = []
        for s in result.get("segments") or []:
            segments.append(
                {
                    "segment_id": f"SEG-{uuid4().hex[:6]}",
                    "start_time": s.get("start_time") or "",
                    "end_time": s.get("end_time") or "",
                    "speaker_id": s.get("speaker_id") or "Speaker 1",
                    "text": s.get("text") or "",
                    "source_type": "gemini",
                    "confidence": s.get("confidence"),  # only if provider sent it
                }
            )
        meeting["transcript"] = {
            "full_text": result.get("full_text") or "",
            "segments": segments,
            "source": "gemini",
            "edited": False,
            "provider": result.get("provider"),
            "model": result.get("model"),
        }
        meeting["transcript_status"] = "ready"
        meeting["status"] = "transcript_ready"
        meeting["transcript_error"] = None
        _put(meeting)
        audit("meeting_intel_transcribed", {"meeting_id": meeting_id, "segments": len(segments)})
        return {"meeting": meeting, "transcript": meeting["transcript"], "is_demo": True}
    except Exception as e:
        meeting["transcript_status"] = "failed"
        meeting["transcript_error"] = str(e)
        _put(meeting)
        return {"error": str(e), "meeting": meeting, "gemini": provider_status()}


def update_transcript(meeting_id: str, body: dict[str, Any]) -> dict[str, Any]:
    meeting = _get(meeting_id)
    if not meeting:
        return {"error": "Meeting not found"}
    tr = meeting.get("transcript") or {"segments": [], "full_text": ""}
    # Keep original once
    if not tr.get("original_segments") and tr.get("segments"):
        tr["original_segments"] = json.loads(json.dumps(tr["segments"]))
    if "segments" in body:
        tr["segments"] = body["segments"]
        tr["full_text"] = " ".join(s.get("text", "") for s in tr["segments"])
        tr["edited"] = True
    if "full_text" in body and "segments" not in body:
        tr["full_text"] = body["full_text"]
        tr["edited"] = True
    meeting["transcript"] = tr
    meeting["transcript_status"] = "ready"
    return _put(meeting)


def _validate_segment_refs(meeting: dict[str, Any], seg_ids: list[str]) -> list[str]:
    valid = {s.get("segment_id") for s in (meeting.get("transcript") or {}).get("segments") or []}
    return [sid for sid in seg_ids if sid in valid]


def generate_minutes(store: DataStore, meeting_id: str) -> dict[str, Any]:
    meeting = _get(meeting_id)
    if not meeting:
        return {"error": "Meeting not found"}
    tr = meeting.get("transcript") or {}
    if not (tr.get("full_text") or tr.get("segments")):
        return {"error": "Transcript not ready — cannot generate minutes"}

    if not gemini_client.is_configured():
        return {
            "error": "GEMINI_API_KEY not configured — minutes generation requires Gemini",
            "gemini": provider_status(),
        }

    meeting["minutes_status"] = "processing"
    meeting["status"] = "processing_minutes"
    _put(meeting)

    snap = investor_snapshot(store, meeting["investor_id"])
    payload = {
        "task": "Generate structured Minutes of Meeting",
        "meeting": {
            "title": meeting.get("title"),
            "type": meeting.get("meeting_type"),
            "purpose": meeting.get("purpose"),
            "agenda": meeting.get("agenda"),
            "participants": meeting.get("participants"),
            "scheduled_at": meeting.get("scheduled_at"),
        },
        "client_context": {
            "investor_id": meeting["investor_id"],
            "display_name": meeting.get("display_name"),
            "goal": (snap.get("goal_progress") or {}).get("goal_name"),
            "priority_reason": None,
        },
        "live_notes": meeting.get("live_notes") or [],
        "transcript_segments": tr.get("segments") or [],
        "transcript_full_text": tr.get("full_text"),
        "schema": {
            "executive_summary": ["bullet strings"],
            "discussion_topics": [
                {
                    "topic": "str",
                    "summary": "str",
                    "client_statements": ["str"],
                    "advisor_advice": ["str"],
                    "outcome": "str",
                    "evidence_segment_ids": ["segment_id"],
                }
            ],
            "client_goals_and_circumstances": [{"item": "str", "is_new": True, "evidence_segment_ids": []}],
            "client_concerns": [
                {
                    "concern": "str",
                    "supporting_statement": "str",
                    "addressed": False,
                    "evidence_segment_ids": [],
                    "evidence_status": "Verified|Limited|Insufficient",
                }
            ],
            "advice_items": [
                {
                    "advice_id": "str",
                    "summary": "str",
                    "rationale": "str",
                    "related_goal_or_asset": "str",
                    "client_response": "agreed|declined|deferred|clarification|unclear",
                    "is_approved_decision": False,
                    "evidence_segment_ids": [],
                    "evidence_status": "Verified|Limited|Insufficient",
                    "follow_up": "str",
                }
            ],
            "decisions": [
                {
                    "decision": "str",
                    "expressed_by": "client|advisor",
                    "status": "agreed|declined|deferred|needs_confirmation|unclear",
                    "evidence_segment_ids": [],
                    "evidence_status": "Verified|Limited|Insufficient",
                }
            ],
            "action_items": [
                {
                    "action_id": "str",
                    "description": "str",
                    "owner": "advisor|client|unassigned",
                    "due_date": None,
                    "priority": "high|medium|low",
                    "explicitly_agreed": True,
                    "evidence_segment_ids": [],
                    "evidence_status": "Verified|Limited|Insufficient",
                }
            ],
            "unresolved_questions": [{"question": "str", "why_it_matters": "str", "owner": "str"}],
            "proposed_client_updates": [
                {
                    "field_name": "str",
                    "previous_value": "str",
                    "proposed_value": "str",
                    "evidence_segment_ids": [],
                    "status": "proposed",
                }
            ],
            "follow_up_draft": "client-facing draft email text",
            "conclusion": {
                "resolved": ["str"],
                "open": ["str"],
                "next_step": "str",
            },
        },
        "rules": [
            "Only use transcript and notes. Do not invent portfolio metrics.",
            "Do not treat silence as agreement.",
            "due_date must be null unless explicitly stated.",
            "evidence_segment_ids must reference provided segment_ids only.",
            "Mark ambiguous items Limited or Insufficient.",
        ],
    }

    try:
        raw = gemini_client.generate_json(json.dumps(payload))
    except Exception as e:
        meeting["minutes_status"] = "failed"
        meeting["minutes_error"] = str(e)
        _put(meeting)
        return {"error": str(e), "gemini": provider_status()}

    # Validate segment refs
    for section in ("discussion_topics", "client_concerns", "advice_items", "decisions", "action_items"):
        for item in raw.get(section) or []:
            ids = item.get("evidence_segment_ids") or []
            item["evidence_segment_ids"] = _validate_segment_refs(meeting, ids)
            if not item.get("evidence_segment_ids") and item.get("evidence_status") == "Verified":
                item["evidence_status"] = "Limited"
                item["verification_note"] = "No valid transcript segment reference — demoted from Verified"

    for item in raw.get("advice_items") or []:
        item.setdefault("advice_id", f"ADV-{uuid4().hex[:6]}")
        item["advisor_approved"] = False
    for item in raw.get("action_items") or []:
        item.setdefault("action_id", f"ACT-{uuid4().hex[:6]}")
        item["advisor_approved"] = False
        item["commitment_id"] = None
        if not item.get("explicitly_agreed"):
            item["suggestion_only"] = True

    minutes = {
        "minutes_id": f"MOM-{uuid4().hex[:8]}",
        "version": int(meeting.get("minutes_version") or 0) + 1,
        "status": "ready_for_review",
        "generated_at": _now(),
        "generator": "google_gemini",
        "executive_summary": raw.get("executive_summary") or [],
        "discussion_topics": raw.get("discussion_topics") or [],
        "client_goals_and_circumstances": raw.get("client_goals_and_circumstances") or [],
        "client_concerns": raw.get("client_concerns") or [],
        "advice_items": raw.get("advice_items") or [],
        "decisions": raw.get("decisions") or [],
        "action_items": raw.get("action_items") or [],
        "unresolved_questions": raw.get("unresolved_questions") or [],
        "proposed_client_updates": raw.get("proposed_client_updates") or [],
        "follow_up_draft": raw.get("follow_up_draft") or "",
        "follow_up_draft_status": "draft_requires_approval",
        "conclusion": raw.get("conclusion") or {},
        "evidence": envelope(
            "AI-generated MoM from transcript — requires advisor approval",
            confidence=ConfidenceLevel.LIMITED,
            evidence=[{"source": "gemini_minutes", "record_ids": [meeting_id]}],
            limitations=["Draft until advisor approves", "Citations validated against segment IDs"],
        ),
    }

    meeting["minutes"] = minutes
    meeting["minutes_version"] = minutes["version"]
    meeting["minutes_status"] = "ready_for_review"
    meeting["status"] = "ready_for_review"
    meeting["minutes_error"] = None
    _put(meeting)
    audit("meeting_intel_minutes", {"meeting_id": meeting_id, "version": minutes["version"]})
    return {"meeting": meeting, "minutes": minutes, "is_demo": True}


def update_minutes(meeting_id: str, patch: dict[str, Any]) -> dict[str, Any]:
    meeting = _get(meeting_id)
    if not meeting or not meeting.get("minutes"):
        return {"error": "Minutes not found"}
    mins = meeting["minutes"]
    for k, v in patch.items():
        if k in {
            "executive_summary",
            "discussion_topics",
            "client_goals_and_circumstances",
            "client_concerns",
            "advice_items",
            "decisions",
            "action_items",
            "unresolved_questions",
            "proposed_client_updates",
            "follow_up_draft",
            "conclusion",
        }:
            mins[k] = v
    mins["status"] = "draft"
    meeting["minutes"] = mins
    meeting["minutes_status"] = "draft"
    return _put(meeting)


def approve_minutes(meeting_id: str, advisor_id: str = "DEMO-ADV-USER-01") -> dict[str, Any]:
    meeting = _get(meeting_id)
    if not meeting or not meeting.get("minutes"):
        return {"error": "Minutes not found"}
    mins = meeting["minutes"]
    mins["status"] = "approved"
    mins["approved_at"] = _now()
    mins["approved_by"] = advisor_id
    meeting["minutes"] = mins
    meeting["minutes_status"] = "approved"
    meeting["status"] = "approved"
    meeting["approved_at"] = mins["approved_at"]
    meeting["approved_by"] = advisor_id
    meeting["ended_at"] = meeting.get("ended_at") or _now()
    _put(meeting)
    audit("meeting_intel_approve", {"meeting_id": meeting_id, "advisor_id": advisor_id})
    return meeting


def create_commitments_from_actions(
    meeting_id: str,
    action_ids: list[str] | None = None,
) -> dict[str, Any]:
    meeting = _get(meeting_id)
    if not meeting or not meeting.get("minutes"):
        return {"error": "Minutes not found"}
    if meeting.get("minutes_status") != "approved":
        return {"error": "Approve minutes before creating commitments"}

    created = []
    for item in meeting["minutes"].get("action_items") or []:
        aid = item.get("action_id")
        if action_ids and aid not in action_ids:
            continue
        if item.get("commitment_id"):
            continue  # idempotent
        if item.get("suggestion_only") and not item.get("advisor_approved"):
            continue
        # Idempotency key
        idem = f"mi::{meeting_id}::{aid}"
        existing = [c for c in load_commitments() if c.get("idempotency_key") == idem]
        if existing:
            item["commitment_id"] = existing[0].get("id")
            continue
        c = upsert_commitment(
            {
                "id": str(uuid4()),
                "investor_id": meeting["investor_id"],
                "action": item.get("description"),
                "status": "open",
                "due": item.get("due_date"),
                "owner": item.get("owner") or "advisor",
                "source": "meeting_intel",
                "meeting_id": meeting_id,
                "action_id": aid,
                "idempotency_key": idem,
                "created_at": _now(),
            }
        )
        item["commitment_id"] = c.get("id")
        item["advisor_approved"] = True
        created.append(c)

    meeting["minutes"]["action_items"] = meeting["minutes"].get("action_items")
    _put(meeting)
    return {"created": created, "meeting": meeting, "is_demo": True}


def end_meeting(meeting_id: str) -> dict[str, Any]:
    meeting = _get(meeting_id)
    if not meeting:
        return {"error": "Meeting not found"}
    meeting["ended_at"] = _now()
    if meeting.get("recording_status") == "recording":
        meeting["recording_status"] = "stopped"
    if meeting.get("status") == "live":
        meeting["status"] = "transcript_ready" if meeting.get("transcript_status") == "ready" else "stopped"
    return _put(meeting)
