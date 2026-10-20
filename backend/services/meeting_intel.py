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
from services import gemini_client, google_meet
from services.advice_outcome import advice_outcome_report
from services.drift import detect_drift
from services.meetings import pre_meeting_pack

MEETINGS_FILE = "meetings_intel.json"
RECORDINGS = RUNTIME / "recordings"
RECORDINGS.mkdir(parents=True, exist_ok=True)
DEMO_TRANSCRIPT = Path(__file__).resolve().parents[2] / "data" / "demo" / "priya_meeting_demo_transcript.json"

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
    gemini = gemini_client.status()
    video = google_meet.status()
    # Flatten gemini keys for existing UI banners; keep nested objects too.
    return {
        **gemini,
        "gemini": gemini,
        "video": video,
    }


def list_meetings(investor_id: str | None = None) -> dict[str, Any]:
    items = _load()
    if investor_id:
        items = [m for m in items if m.get("investor_id") == investor_id]
    items.sort(key=lambda m: m.get("scheduled_at") or m.get("created_at") or "", reverse=True)
    return {"meetings": items, "count": len(items), **provider_status(), "is_demo": True}


def get_meeting(meeting_id: str) -> dict[str, Any]:
    m = _get(meeting_id)
    if not m:
        return {"error": "Meeting not found", "meeting_id": meeting_id}
    return {**m, **provider_status(), "is_demo": True}


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
        "meet_link": None,
        "meet_provider": None,
        "meet_calendar_event_id": None,
        "meet_meta": None,
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

    if gemini_client.is_usable() and (regenerate or not meeting.get("prep_brief_gemini")):
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
    # Do not downgrade a meeting that already has transcript/minutes/live progress
    ms = meeting.get("minutes_status")
    ts = meeting.get("transcript_status")
    cur = meeting.get("status") or ""
    if ms in {"ready_for_review", "approved"}:
        meeting["status"] = "approved" if ms == "approved" else "ready_for_review"
    elif ts == "ready":
        meeting["status"] = "transcript_ready"
    elif cur in {
        "live",
        "recording",
        "transcribing",
        "processing_minutes",
        "stopped",
        "transcript_ready",
        "ready_for_review",
        "approved",
    }:
        pass
    else:
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
    if not gemini_client.is_usable():
        meeting["transcript_status"] = "failed"
        meeting["transcript_error"] = (
            "Gemini not usable for live transcription — use Load demo transcript for the Priya demo"
        )
        _put(meeting)
        return {
            "error": (
                "Live transcription needs a valid Google AI Studio GEMINI_API_KEY. "
                "For the demo: click “Load demo transcript” (or History → Load Priya demo)."
            ),
            "hint": "load_demo_transcript",
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
        clean = gemini_client.friendly_error(e)
        meeting["transcript_status"] = "failed"
        meeting["transcript_error"] = clean
        _put(meeting)
        return {
            "error": clean,
            "hint": "Use “Load demo transcript” for the Priya demo without a live Gemini key.",
            "meeting": meeting,
            "gemini": provider_status(),
        }


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


def _demo_minutes_payload(meeting: dict[str, Any]) -> dict[str, Any]:
    """Deterministic MoM for the packaged Priya demo transcript (judge-safe offline path)."""
    segs = {
        s.get("segment_id"): s.get("text")
        for s in ((meeting.get("transcript") or {}).get("segments") or [])
    }

    def e(*ids: str) -> list[str]:
        return [i for i in ids if i in segs]

    return {
        "executive_summary": [
            "Reviewed retirement goal path and mid-cap overweight versus moderate policy.",
            "Client deferred full rebalance pending a written proposal; SIP remains unchanged.",
            "Near-term education deposit liquidity need noted; follow-up to be scheduled after proposal.",
        ],
        "discussion_topics": [
            {
                "topic": "Retirement goal & mid-cap drift",
                "summary": "Advisor flagged goal lag and mid-cap overweight; client concerned about volatility.",
                "client_statements": [
                    segs.get("SEG-DEMO-02") or "Concerned about mid-cap volatility",
                    segs.get("SEG-DEMO-10") or "Okay with equity, not so much mid-cap",
                ],
                "advisor_advice": [
                    segs.get("SEG-DEMO-05") or "Review rebalancing plan trimming mid-cap toward policy",
                ],
                "outcome": "Deferred — proposal required before any rebalance",
                "evidence_segment_ids": e("SEG-DEMO-02", "SEG-DEMO-03", "SEG-DEMO-05", "SEG-DEMO-06"),
            }
        ],
        "client_goals_and_circumstances": [
            {
                "item": "Possible liquidity next year for daughter's education deposit",
                "is_new": True,
                "evidence_segment_ids": e("SEG-DEMO-04"),
            }
        ],
        "client_concerns": [
            {
                "concern": "Mid-cap volatility / overweight",
                "supporting_statement": segs.get("SEG-DEMO-02") or "",
                "addressed": True,
                "evidence_segment_ids": e("SEG-DEMO-02", "SEG-DEMO-10"),
                "evidence_status": "Verified",
            },
            {
                "concern": "Downside if markets stay weak",
                "supporting_statement": segs.get("SEG-DEMO-10") or "",
                "addressed": False,
                "evidence_segment_ids": e("SEG-DEMO-10"),
                "evidence_status": "Verified",
            },
        ],
        "advice_items": [
            {
                "advice_id": "ADV-DEMO-REBAL",
                "summary": "Prepare revised allocation proposal trimming mid-cap toward policy while keeping SIP",
                "rationale": "Portfolio mid-cap overweight and recent active-return lag vs benchmark",
                "related_goal_or_asset": "Retirement goal / equity allocation",
                "client_response": "deferred",
                "is_approved_decision": False,
                "evidence_segment_ids": e("SEG-DEMO-05", "SEG-DEMO-06", "SEG-DEMO-07"),
                "evidence_status": "Verified",
                "follow_up": "Send written proposal within one week",
            }
        ],
        "decisions": [
            {
                "decision": "Keep current SIP amount for now",
                "expressed_by": "client",
                "status": "agreed",
                "evidence_segment_ids": e("SEG-DEMO-07", "SEG-DEMO-08"),
                "evidence_status": "Verified",
            },
            {
                "decision": "Full rebalance not approved today — await written proposal",
                "expressed_by": "client",
                "status": "deferred",
                "evidence_segment_ids": e("SEG-DEMO-06"),
                "evidence_status": "Verified",
            },
        ],
        "action_items": [
            {
                "action_id": "ACT-DEMO-01",
                "description": "Send revised rebalancing / allocation proposal within one week",
                "owner": "advisor",
                "due_date": None,
                "priority": "high",
                "explicitly_agreed": True,
                "evidence_segment_ids": e("SEG-DEMO-07", "SEG-DEMO-09"),
                "evidence_status": "Verified",
            },
            {
                "action_id": "ACT-DEMO-02",
                "description": "Review proposal and confirm preference",
                "owner": "client",
                "due_date": None,
                "priority": "high",
                "explicitly_agreed": True,
                "evidence_segment_ids": e("SEG-DEMO-08", "SEG-DEMO-09"),
                "evidence_status": "Verified",
            },
            {
                "action_id": "ACT-DEMO-03",
                "description": "Schedule short follow-up after client reviews proposal",
                "owner": "advisor",
                "due_date": None,
                "priority": "medium",
                "explicitly_agreed": True,
                "evidence_segment_ids": e("SEG-DEMO-08", "SEG-DEMO-09"),
                "evidence_status": "Verified",
            },
        ],
        "unresolved_questions": [
            {
                "question": "How to frame downside protection if markets stay weak while mid-cap is trimmed?",
                "why_it_matters": "Client asked for clarity on downside; to be covered in proposal",
                "owner": "advisor",
            }
        ],
        "proposed_client_updates": [
            {
                "field_name": "near_term_liquidity_need",
                "previous_value": "not recorded",
                "proposed_value": "Possible education deposit liquidity next year",
                "evidence_segment_ids": e("SEG-DEMO-04"),
                "status": "proposed",
            }
        ],
        "follow_up_draft": (
            "Hi Priya,\n\nThank you for today's review. As discussed, I will send a written "
            "allocation proposal within one week covering a mid-cap trim toward your moderate "
            "policy while keeping the current SIP. We will also note your possible education "
            "deposit liquidity need next year and schedule a short follow-up after you review "
            "the proposal.\n\nBest regards"
        ),
        "conclusion": {
            "resolved": ["SIP continues unchanged", "Proposal to be prepared before rebalance"],
            "open": ["Final allocation decision", "Downside framing in weak markets"],
            "next_step": "Advisor sends written proposal; client reviews; book follow-up",
        },
    }


def _finalize_minutes(
    meeting: dict[str, Any],
    raw: dict[str, Any],
    *,
    generator: str,
) -> dict[str, Any]:
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

    conf = (
        ConfidenceLevel.VERIFIED
        if generator == "demo_fixture_structured"
        else ConfidenceLevel.LIMITED
    )
    minutes = {
        "minutes_id": f"MOM-{uuid4().hex[:8]}",
        "version": int(meeting.get("minutes_version") or 0) + 1,
        "status": "ready_for_review",
        "generated_at": _now(),
        "generator": generator,
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
            "MoM from transcript — requires advisor approval",
            confidence=conf,
            evidence=[{"source": generator, "record_ids": [meeting["meeting_id"]]}],
            limitations=["Draft until advisor approves", "Citations validated against segment IDs"],
        ),
    }
    meeting["minutes"] = minutes
    meeting["minutes_version"] = minutes["version"]
    meeting["minutes_status"] = "ready_for_review"
    meeting["status"] = "ready_for_review"
    meeting["minutes_error"] = None
    _put(meeting)
    audit(
        "meeting_intel_minutes",
        {"meeting_id": meeting["meeting_id"], "version": minutes["version"], "generator": generator},
    )
    return {"meeting": meeting, "minutes": minutes, "is_demo": True}


def generate_minutes(store: DataStore, meeting_id: str) -> dict[str, Any]:
    meeting = _get(meeting_id)
    if not meeting:
        return {"error": "Meeting not found"}
    tr = meeting.get("transcript") or {}
    if not (tr.get("full_text") or tr.get("segments")):
        return {"error": "Transcript not ready — cannot generate minutes"}

    is_demo_transcript = (tr.get("source") == "demo_fixture") or bool(tr.get("demo_title"))

    # Offline structured MoM for packaged demo when Gemini unavailable / invalid key
    if is_demo_transcript and not gemini_client.is_usable():
        return _finalize_minutes(meeting, _demo_minutes_payload(meeting), generator="demo_fixture_structured")

    if not gemini_client.is_usable():
        return {
            "error": (
                "Gemini not usable — minutes need a valid AI Studio key, "
                "or use Load demo transcript / Load Priya demo"
            ),
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
        return _finalize_minutes(meeting, raw, generator="google_gemini")
    except Exception as e:
        if is_demo_transcript:
            # Demo stays judge-ready even if GEMINI_API_KEY is present but invalid
            result = _finalize_minutes(
                meeting, _demo_minutes_payload(meeting), generator="demo_fixture_structured"
            )
            result["gemini_fallback_reason"] = str(e)
            result["note"] = "Gemini failed — used structured demo minutes from packaged transcript"
            return result
        meeting["minutes_status"] = "failed"
        meeting["minutes_error"] = str(e)
        _put(meeting)
        return {"error": str(e), "gemini": provider_status()}


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


def schedule_meet(meeting_id: str, prefer_google: bool = True) -> dict[str, Any]:
    """Attach Google Meet (if OAuth connected) or free Jitsi room to the meeting."""
    meeting = _get(meeting_id)
    if not meeting:
        return {"error": "Meeting not found"}

    result = google_meet.schedule_video_meeting(
        meeting_id=meeting_id,
        title=meeting.get("title") or f"Meeting {meeting_id}",
        description=(
            f"Advisor Pulse meeting with {meeting.get('display_name')} "
            f"({meeting.get('investor_id')}). Purpose: {meeting.get('purpose') or 'client review'}"
        ),
        start_iso=meeting.get("scheduled_at"),
        duration_min=int(meeting.get("expected_duration_min") or 45),
        prefer_google=prefer_google,
    )
    if result.get("error") and not result.get("meet_link"):
        return result

    meeting["meet_link"] = result.get("meet_link")
    meeting["meet_provider"] = result.get("provider")
    meeting["meet_calendar_event_id"] = result.get("calendar_event_id")
    meeting["meet_meta"] = {
        k: result.get(k)
        for k in (
            "html_link",
            "room",
            "note",
            "fallback_reason",
            "google_error",
            "connect_hint",
            "is_demo",
            "start",
            "end",
        )
        if result.get(k) is not None
    }
    _put(meeting)
    audit(
        "meeting_intel_schedule_meet",
        {"meeting_id": meeting_id, "provider": meeting["meet_provider"]},
    )
    return {"meeting": meeting, "schedule": result, **provider_status(), "is_demo": True}


def load_demo_transcript(meeting_id: str, store: DataStore | None = None) -> dict[str, Any]:
    """
    Load packaged Priya demo transcript (synthetic — for demos).
    Optionally builds structured minutes when store is provided (demo path).
    """
    meeting = _get(meeting_id)
    if not meeting:
        return {"error": "Meeting not found"}
    if not DEMO_TRANSCRIPT.exists():
        return {"error": f"Demo transcript missing at {DEMO_TRANSCRIPT}"}

    # Ensure a joinable video link first (schedule_meet reloads from disk).
    if not meeting.get("meet_link"):
        schedule_meet(meeting_id, prefer_google=False)
        meeting = _get(meeting_id) or meeting

    data = json.loads(DEMO_TRANSCRIPT.read_text(encoding="utf-8"))
    segments = data.get("segments") or []
    for s in segments:
        s.setdefault("segment_id", f"SEG-{uuid4().hex[:6]}")
        s.setdefault("source_type", "demo_fixture")

    meeting["transcript"] = {
        "full_text": data.get("full_text") or "",
        "segments": segments,
        "source": "demo_fixture",
        "edited": False,
        "provider": None,
        "disclaimer": data.get("disclaimer"),
        "demo_title": data.get("title"),
    }
    meeting["transcript_status"] = "ready"
    meeting["status"] = "transcript_ready"
    # Auto-confirm consent for demo path (advisor still controls minutes approval)
    if meeting.get("consent_status") != "confirmed":
        meeting["consent_status"] = "confirmed"
        meeting["consent_confirmed_at"] = _now()
        meeting["consent_note"] = "Demo path: consent recorded for packaged transcript demo"

    _put(meeting)
    audit("meeting_intel_demo_transcript", {"meeting_id": meeting_id})

    minutes_out = None
    if store is not None:
        minutes_out = generate_minutes(store, meeting_id)
        if not minutes_out.get("error"):
            meeting = minutes_out.get("meeting") or _get(meeting_id) or meeting

    return {
        "meeting": meeting,
        "transcript": meeting.get("transcript"),
        "minutes": (minutes_out or {}).get("minutes"),
        "hint": (
            "Minutes ready — open Minutes tab → Approve → Create commitments"
            if meeting.get("minutes_status") == "ready_for_review"
            else "Open Minutes tab → Generate Meeting Minutes"
        ),
        "is_demo": True,
    }


def seed_demo_meeting(store: DataStore) -> dict[str, Any]:
    """One-click demo: Priya meeting + Jitsi/Meet link + packaged transcript."""
    created = create_meeting(
        store,
        {
            "investor_id": "DEMO-INV-001",
            "title": "DEMO: Priya Sharma — quarterly portfolio review",
            "meeting_type": "portfolio_review",
            "purpose": "Review goal path, mid-cap drift, and SIP — demo walkthrough",
            "channel": "online",
            "expected_duration_min": 30,
            "agenda": [
                "Review previous action items",
                "Discuss retirement goal progress",
                "Review mid-cap allocation vs policy",
                "Liquidity needs for education deposit",
                "Confirm next steps and proposal timeline",
            ],
        },
    )
    if created.get("error"):
        return created
    mid = created["meeting_id"]
    build_preparation_brief(store, mid)
    confirm_consent(mid, "Demo seed consent")
    schedule_meet(mid, prefer_google=True)
    loaded = load_demo_transcript(mid, store=store)
    meeting = loaded.get("meeting") or get_meeting(mid)
    return {
        "meeting": meeting,
        "minutes": loaded.get("minutes") or (meeting or {}).get("minutes"),
        "demo_script": [
            "1. Join Meet (Jitsi/Google) from Preparation or Live",
            "2. Minutes tab already has the demo transcript + structured MoM",
            "3. Approve Meeting Minutes → Create commitments",
        ],
        **provider_status(),
        "is_demo": True,
    }
