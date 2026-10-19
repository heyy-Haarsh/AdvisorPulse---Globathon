"""
Advisor Pulse API — Globathon FinTech prototype.
All investment metrics computed from DEMO synthetic data unless noted.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from agents.coordinator import run_analysis
from analytics.portfolio import DataStore, investor_snapshot
from analytics.quantstats_bridge import performance_crosscheck
from domain.persistence import (
    load_audit,
    load_settings,
    save_decision,
    save_settings,
)
from eval.alert_quality import evaluate as evaluate_alert_quality
from ingestion.transactions import cashflow_signals, load_transactions
from prioritization.engine import overview_kpis, rank_book, score_investor
from services import (
    advice_outcome,
    blind_spot,
    client_summary,
    copilot,
    drift,
    feedback,
    meeting_intel,
    meetings,
    memory,
    patterns,
    review_action,
    txn_quality,
    whatif,
)
from summaries.generator import generate, meeting_brief

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

_store: DataStore | None = None
_ranked_cache: list[dict[str, Any]] | None = None


def to_jsonable(obj: Any) -> Any:
    """Convert numpy/pandas scalars so FastAPI can encode responses."""
    if obj is None:
        return None
    if isinstance(obj, dict):
        return {str(k): to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [to_jsonable(v) for v in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        val = float(obj)
        return None if np.isnan(val) else val
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if isinstance(obj, np.ndarray):
        return to_jsonable(obj.tolist())
    if isinstance(obj, pd.Timestamp):
        return obj.isoformat()
    if isinstance(obj, float) and (obj != obj):  # NaN
        return None
    if pd.isna(obj) if not isinstance(obj, (str, bytes, dict, list)) else False:
        try:
            if pd.isna(obj):
                return None
        except (TypeError, ValueError):
            pass
    return obj


app = FastAPI(
    title="Advisor Pulse API",
    description="AI-powered advisor intelligence platform (DEMO)",
    version="0.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def store() -> DataStore:
    global _store
    if _store is None:
        _store = DataStore.load()
    return _store


def invalidate_rank_cache() -> None:
    global _ranked_cache, _store
    _ranked_cache = None


def invalidate_store() -> None:
    global _store, _ranked_cache
    _store = None
    _ranked_cache = None


def ranked(include_resolved: bool = True) -> list[dict[str, Any]]:
    global _ranked_cache
    if _ranked_cache is None:
        _ranked_cache = rank_book(store(), include_resolved=True)
    return _ranked_cache


# ---------- request models ----------


class NoteIn(BaseModel):
    investor_id: str
    note_text: str = Field(min_length=1, max_length=4000)
    author: str = "DEMO-ADV-USER-01"


class NoteUpdate(BaseModel):
    note_text: str = Field(min_length=1, max_length=4000)


class TranscriptIn(BaseModel):
    investor_id: str
    audio_filename: str = "mock_meeting.wav"
    mock_transcript: str | None = None


class AttentionDecisionIn(BaseModel):
    investor_id: str
    action: str = Field(description="reviewed | dismiss | follow_up | reopen")
    note: str | None = None


class DriftStatusIn(BaseModel):
    status: str
    note: str = ""


class WhatIfIn(BaseModel):
    sip_delta: float = 0.0
    return_delta_pp: float = 0.0
    years_override: float | None = None
    lump_sum: float = 0.0
    scenario_type: str = "sip_contribution"
    proposed_weights: dict[str, float] | None = None
    market_shocks: dict[str, float] | None = None


class CopilotIn(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    context_investor_id: str | None = None
    advisor_id: str = "DEMO-ADV-USER-01"


class FeedbackIn(BaseModel):
    investor_id: str
    insight_ref: str
    action: str
    correction: str | None = None
    note: str | None = None


class ConfirmExtractionIn(BaseModel):
    create_followup: bool = True


class PostMeetingIn(BaseModel):
    notes_text: str = Field(min_length=1, max_length=8000)


class CommitmentIn(BaseModel):
    investor_id: str
    action: str
    due: str | None = None
    commitment_id: str | None = None
    status: str = "open"


class SettingsIn(BaseModel):
    weights: dict[str, float] | None = None
    goal_deviation_critical_pct: float | None = None
    goal_deviation_high_pct: float | None = None
    active_return_high_pp: float | None = None
    stale_data_days: int | None = None
    stale_review_days: int | None = None
    note_retention_days: int | None = None
    accessible_clients: list[str] | None = None


class ReviewActionDecisionIn(BaseModel):
    decision: str = Field(description="accept | edit | reject")
    action_key: str | None = None
    action_label: str | None = None
    note: str = ""
    approve_client_message: bool = False


class ExceptionResolveIn(BaseModel):
    resolution: str = Field(description="confirm_duplicate | ignore | apply_suggestion | dismiss")
    note: str = ""


class MeetingCreateIn(BaseModel):
    investor_id: str
    title: str | None = None
    meeting_type: str = "portfolio_review"
    scheduled_at: str | None = None
    expected_duration_min: int = 45
    participants: list[str] | None = None
    channel: str = "online"
    purpose: str = ""
    advisor_prep_notes: str = ""
    agenda: list[str] | None = None
    custom_questions: list[str] | None = None


class MeetingPatchIn(BaseModel):
    title: str | None = None
    meeting_type: str | None = None
    scheduled_at: str | None = None
    expected_duration_min: int | None = None
    participants: list[str] | None = None
    channel: str | None = None
    purpose: str | None = None
    advisor_prep_notes: str | None = None
    agenda: list[str] | None = None
    custom_questions: list[str] | None = None
    checklist: list[dict] | None = None
    status: str | None = None


class ConsentIn(BaseModel):
    note: str = ""


class LiveNoteIn(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    category: str = "general"
    timestamp: str | None = None
    linked_segment_ids: list[str] | None = None


class TranscriptPasteIn(BaseModel):
    text: str = Field(min_length=1, max_length=200000)
    segments: list[dict] | None = None


class TranscriptUpdateIn(BaseModel):
    full_text: str | None = None
    segments: list[dict] | None = None


class MinutesPatchIn(BaseModel):
    executive_summary: list | None = None
    discussion_topics: list | None = None
    client_concerns: list | None = None
    advice_items: list | None = None
    decisions: list | None = None
    action_items: list | None = None
    unresolved_questions: list | None = None
    proposed_client_updates: list | None = None
    follow_up_draft: str | None = None
    conclusion: dict | None = None


class CommitmentsFromActionsIn(BaseModel):
    action_ids: list[str] | None = None


# ---------- core endpoints ----------


@app.get("/api/health")
def health():
    s = store()
    return {
        "status": "ok",
        "product": "Advisor Pulse",
        "version": "0.2.0",
        "investors_loaded": len(s.investors),
        "is_demo": True,
        "features": [
            "attention_engine",
            "advice_outcome",
            "structured_summary",
            "advisor_memory",
            "drift_detector",
            "multi_agent",
            "copilot",
            "whatif",
            "patterns",
            "meeting_prep",
            "evidence_guard",
            "feedback_loop",
            "blind_spot_radar",
            "alert_quality_lab",
            "next_review_action",
            "txn_data_quality",
            "meeting_intelligence",
        ],
        "gemini": meeting_intel.provider_status(),
    }


@app.get("/api/overview")
def overview():
    r = ranked()
    kpis = overview_kpis(r)
    for item in kpis["action_queue"]:
        dec = item.get("decision") or {}
        item["marked_reviewed"] = dec.get("action") == "reviewed"
        item["decision_action"] = dec.get("action")
    return JSONResponse(to_jsonable(kpis))


@app.get("/api/attention")
def attention(
    priority: str | None = None,
    tier: str | None = None,
    goal_behind: bool | None = None,
    stale_review: bool | None = None,
    data_issue: bool | None = None,
    include_resolved: bool = False,
    min_confidence: str | None = None,
):
    rows = ranked()
    out = []
    for row in rows:
        if not include_resolved and row.get("resolved"):
            continue
        if priority and row["priority"].lower() != priority.lower():
            continue
        if tier and row["tier"] != tier:
            continue
        if goal_behind is True and row["goal_status"]["deviation_pct_vs_expected"] >= -5:
            continue
        if stale_review is True:
            if not any(f["name"] == "stale_review" and f["points"] > 0 for f in row["factors"]):
                continue
        if data_issue is True and not row.get("data_quality_issue"):
            continue
        if min_confidence:
            order = {"Insufficient": 0, "Limited": 1, "Verified": 2}
            if order.get(row.get("confidence", "Limited"), 1) < order.get(min_confidence, 0):
                continue
        item = dict(row)
        dec = item.get("decision") or {}
        item["marked_reviewed"] = dec.get("action") == "reviewed"
        item["decision_action"] = dec.get("action")
        out.append(item)
    return JSONResponse(to_jsonable({"count": len(out), "clients": out, "is_demo": True}))


@app.post("/api/attention/decision")
def attention_decision(body: AttentionDecisionIn):
    if body.action not in {"reviewed", "dismiss", "follow_up", "reopen"}:
        raise HTTPException(400, "action must be reviewed|dismiss|follow_up|reopen")
    action = "reopen" if body.action == "reopen" else body.action
    if action == "reopen":
        record = save_decision(
            body.investor_id,
            {"investor_id": body.investor_id, "action": "reopen", "note": body.note},
        )
    else:
        record = save_decision(
            body.investor_id,
            {"investor_id": body.investor_id, "action": action, "note": body.note},
        )
    invalidate_rank_cache()
    return to_jsonable(record)


class ReviewedIn(BaseModel):
    investor_id: str
    reviewed: bool = True


@app.post("/api/attention/reviewed")
def mark_reviewed_compat(body: ReviewedIn):
    """Backward-compatible reviewed flag → persisted decision."""
    record = save_decision(
        body.investor_id,
        {
            "investor_id": body.investor_id,
            "action": "reviewed" if body.reviewed else "reopen",
        },
    )
    invalidate_rank_cache()
    return {
        "investor_id": body.investor_id,
        "marked_reviewed": body.reviewed,
        "decision": record,
    }


@app.get("/api/clients")
def list_clients(q: str | None = None, tier: str | None = None, limit: int = 100):
    rows = ranked()
    out = []
    ql = (q or "").lower()
    for row in rows:
        if tier and row["tier"] != tier:
            continue
        if ql and ql not in row["display_name"].lower() and ql not in row["investor_id"].lower():
            continue
        out.append(
            {
                "investor_id": row["investor_id"],
                "display_name": row["display_name"],
                "tier": row["tier"],
                "risk_profile": row["risk_profile"],
                "priority": row["priority"],
                "score": row["score"],
                "confidence": row.get("confidence"),
                "goal_status": row["goal_status"],
            }
        )
        if len(out) >= limit:
            break
    return JSONResponse(to_jsonable({"count": len(out), "clients": out, "is_demo": True}))


@app.get("/api/investors/{investor_id}")
def get_investor(investor_id: str):
    snap = investor_snapshot(store(), investor_id)
    if snap.get("error"):
        raise HTTPException(404, snap["error"])
    pri = score_investor(store(), investor_id)
    summary = generate(snap, pri)
    structured = client_summary.build_structured_summary(store(), investor_id)
    ao = advice_outcome.advice_outcome_report(store(), investor_id)
    drift_report = drift.detect_drift(store(), investor_id)
    return JSONResponse(
        to_jsonable(
            {
                "snapshot": snap,
                "priority": pri,
                "summary": summary,
                "structured_summary": structured,
                "advice_outcomes": ao,
                "drift": drift_report,
                "marked_reviewed": (pri.get("decision") or {}).get("action") == "reviewed",
            }
        )
    )


@app.get("/api/investors/{investor_id}/summary")
def get_structured_summary(investor_id: str):
    result = client_summary.build_structured_summary(store(), investor_id)
    if result.get("error"):
        raise HTTPException(404, result["error"])
    return JSONResponse(to_jsonable(result))


@app.get("/api/investors/{investor_id}/advice-outcomes")
def get_advice_outcomes(investor_id: str):
    return JSONResponse(to_jsonable(advice_outcome.advice_outcome_report(store(), investor_id)))


@app.get("/api/investors/{investor_id}/drift")
def get_drift(investor_id: str):
    return JSONResponse(to_jsonable(drift.detect_drift(store(), investor_id)))


@app.post("/api/drift/{alert_id}/status")
def set_drift_status(alert_id: str, body: DriftStatusIn):
    try:
        return to_jsonable(drift.update_drift_status(alert_id, body.status, body.note))
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@app.post("/api/investors/{investor_id}/whatif")
def run_whatif(investor_id: str, body: WhatIfIn):
    return JSONResponse(
        to_jsonable(
            whatif.simulate_scenario(
                store(),
                investor_id,
                scenario_type=body.scenario_type,
                sip_delta=body.sip_delta,
                return_delta_pp=body.return_delta_pp,
                years_override=body.years_override,
                lump_sum=body.lump_sum,
                proposed_weights=body.proposed_weights,
                market_shocks=body.market_shocks,
            )
        )
    )


@app.get("/api/investors/{investor_id}/agents")
def get_agents(investor_id: str):
    return JSONResponse(to_jsonable(run_analysis(store(), investor_id)))


@app.get("/api/investors/{investor_id}/timeline")
def get_timeline(investor_id: str):
    return JSONResponse(to_jsonable(feedback.timeline(store(), investor_id)))


@app.post("/api/feedback")
def post_feedback(body: FeedbackIn):
    try:
        return to_jsonable(
            feedback.record_feedback(
                body.investor_id,
                body.insight_ref,
                body.action,
                correction=body.correction,
                note=body.note,
            )
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@app.get("/api/investors/{investor_id}/meeting-brief")
def get_brief(investor_id: str):
    snap = investor_snapshot(store(), investor_id)
    if snap.get("error"):
        raise HTTPException(404, snap["error"])
    pri = score_investor(store(), investor_id)
    summary = generate(snap, pri)
    return JSONResponse(to_jsonable(meeting_brief(snap, pri, summary)))


@app.get("/api/investors/{investor_id}/meeting-prep")
def get_meeting_prep(investor_id: str):
    pack = meetings.pre_meeting_pack(store(), investor_id)
    if pack.get("error"):
        raise HTTPException(404, pack["error"])
    return JSONResponse(to_jsonable(pack))


@app.post("/api/investors/{investor_id}/meeting-followup")
def post_meeting_followup(investor_id: str, body: PostMeetingIn):
    return JSONResponse(to_jsonable(meetings.draft_post_meeting_actions(store(), investor_id, body.notes_text)))


@app.get("/api/commitments")
def get_commitments(investor_id: str | None = None):
    return JSONResponse(to_jsonable(meetings.list_commitments(investor_id)))


@app.post("/api/commitments")
def post_commitment(body: CommitmentIn):
    return to_jsonable(
        meetings.confirm_commitment(
            body.investor_id,
            body.action,
            due=body.due,
            commitment_id=body.commitment_id,
            status=body.status,
        )
    )


@app.get("/api/notes")
def list_notes(investor_id: str | None = None):
    s = store()
    seed = s.notes.to_dict(orient="records")
    return JSONResponse(to_jsonable(memory.list_memory(investor_id, seed)))


@app.post("/api/notes")
def add_note(body: NoteIn):
    return to_jsonable(memory.add_note(body.investor_id, body.note_text, body.author))


@app.put("/api/notes/{note_id}")
def update_note(note_id: str, body: NoteUpdate):
    from datetime import datetime

    notes = memory.load_notes_runtime() if hasattr(memory, "load_notes_runtime") else None
    from domain.persistence import load_notes_runtime, save_notes_runtime

    notes = load_notes_runtime()
    for n in notes:
        if n["note_id"] == note_id:
            n["note_text"] = body.note_text
            n["updated_at"] = datetime.utcnow().isoformat() + "Z"
            save_notes_runtime(notes)
            return n
    raise HTTPException(404, "Runtime note not found (seed CSV notes are read-only in demo)")


@app.post("/api/transcription/mock-local")
def mock_local_transcription(body: TranscriptIn):
    return to_jsonable(
        memory.mock_transcribe(body.investor_id, body.mock_transcript, body.audio_filename)
    )


@app.post("/api/memory/extractions/{extraction_id}/confirm")
def confirm_extraction(extraction_id: str, body: ConfirmExtractionIn | None = None):
    create = True if body is None else body.create_followup
    try:
        result = memory.confirm_extraction(extraction_id, create_followup=create)
        invalidate_rank_cache()
        return to_jsonable(result)
    except KeyError:
        raise HTTPException(404, "Extraction not found") from None


@app.post("/api/memory/extractions/{extraction_id}/dismiss")
def dismiss_extraction(extraction_id: str):
    try:
        return to_jsonable(memory.dismiss_extraction(extraction_id))
    except KeyError:
        raise HTTPException(404, "Extraction not found") from None


@app.post("/api/copilot")
def copilot_query(body: CopilotIn):
    return JSONResponse(
        to_jsonable(
            copilot.route_query(
                store(),
                body.query,
                context_investor_id=body.context_investor_id,
                advisor_id=body.advisor_id,
            )
        )
    )


@app.get("/api/patterns")
def get_patterns():
    return JSONResponse(to_jsonable(patterns.discover_patterns(store())))


@app.get("/api/patterns/{cohort_id}")
def get_pattern(cohort_id: str):
    result = patterns.cohort_detail(store(), cohort_id)
    if result.get("error"):
        raise HTTPException(404, result["error"])
    return JSONResponse(to_jsonable(result))


@app.get("/api/blind-spot")
def get_blind_spot(segment: str | None = "less_observed"):
    """Long-Tail Blind Spot Radar — attention need × review obscurity."""
    invalidate_rank_cache()
    return JSONResponse(to_jsonable(blind_spot.build_radar(store(), segment=segment)))


@app.get("/api/eval/alert-quality")
def alert_quality_lab():
    """Pulse vs CRM-ish baseline metrics on labeled DEMO scenarios."""
    invalidate_rank_cache()
    return JSONResponse(to_jsonable(evaluate_alert_quality(store())))


@app.get("/api/investors/{investor_id}/next-review-action")
def get_next_review_action(investor_id: str):
    pack = review_action.build_pack(store(), investor_id)
    if pack.get("error"):
        raise HTTPException(404, pack["error"])
    return JSONResponse(to_jsonable(pack))


@app.post("/api/investors/{investor_id}/next-review-action/decision")
def post_next_review_action(investor_id: str, body: ReviewActionDecisionIn):
    if body.decision not in {"accept", "edit", "reject"}:
        raise HTTPException(400, "decision must be accept|edit|reject")
    result = review_action.decide_pack(
        store(),
        investor_id,
        decision=body.decision,
        action_key=body.action_key,
        action_label=body.action_label,
        note=body.note,
        approve_client_message=body.approve_client_message,
    )
    invalidate_rank_cache()
    return JSONResponse(to_jsonable(result))


@app.get("/api/investors/{investor_id}/performance-crosscheck")
def get_performance_crosscheck(investor_id: str):
    return JSONResponse(to_jsonable(performance_crosscheck(store(), investor_id)))


@app.get("/api/transactions/signals")
def transaction_signals():
    return JSONResponse(to_jsonable(txn_quality.active_signals()))


@app.post("/api/transactions/validate")
async def transactions_validate(file: UploadFile = File(...)):
    content = await file.read()
    return JSONResponse(to_jsonable(txn_quality.validate_bytes(content, file.filename or "upload.csv")))


@app.post("/api/transactions/validate-demo-dirty")
def transactions_validate_demo_dirty():
    """Load the packaged dirty 10-row fixture through the DQ pipeline."""
    path = DATA / "sample_transactions_dirty.csv"
    return JSONResponse(to_jsonable(txn_quality.validate_path(path)))


@app.get("/api/transactions/exceptions")
def transactions_exceptions():
    return JSONResponse(to_jsonable({"exceptions": txn_quality.list_exceptions(), "is_demo": True}))


@app.post("/api/transactions/exceptions/{exception_id}/resolve")
def transactions_resolve(exception_id: str, body: ExceptionResolveIn):
    try:
        return JSONResponse(
            to_jsonable(txn_quality.resolve_exception(exception_id, body.resolution, body.note))
        )
    except KeyError:
        raise HTTPException(404, "Exception not found") from None


@app.post("/api/transactions/import")
def transactions_import():
    try:
        return JSONResponse(to_jsonable(txn_quality.import_staged()))
    except FileNotFoundError as e:
        raise HTTPException(400, str(e)) from e


@app.get("/api/settings")
def get_settings():
    return to_jsonable(load_settings())


@app.put("/api/settings")
def put_settings(body: SettingsIn):
    patch = {k: v for k, v in body.model_dump().items() if v is not None}
    result = save_settings(patch)
    invalidate_rank_cache()
    return to_jsonable(result)


@app.get("/api/audit")
def get_audit(limit: int = 50):
    return {"entries": load_audit(limit), "is_demo": True}


@app.get("/api/demo/scenario")
def demo_scenario():
    snap1 = investor_snapshot(store(), "DEMO-INV-001")
    pri1 = score_investor(store(), "DEMO-INV-001")
    snap2 = investor_snapshot(store(), "DEMO-INV-002")
    pri2 = score_investor(store(), "DEMO-INV-002")
    snap3 = investor_snapshot(store(), "DEMO-INV-L017")
    pri3 = score_investor(store(), "DEMO-INV-L017")
    return JSONResponse(
        to_jsonable(
            {
                "primary": {
                    "title": "Priya Sharma — detect → explain → prioritize → prepare",
                    "investor_id": "DEMO-INV-001",
                    "data": {
                        "snapshot": snap1,
                        "priority": pri1,
                        "summary": generate(snap1, pri1),
                    },
                },
                "contrast": {
                    "title": "Arjun Mehta — concerning at first glance, not escalated",
                    "investor_id": "DEMO-INV-002",
                    "data": {
                        "snapshot": snap2,
                        "priority": pri2,
                        "summary": generate(snap2, pri2),
                    },
                    "why_not_escalated": (
                        "Absolute AUM dip explained by planned education withdrawal; "
                        "goal path and TWR remain acceptable under configured thresholds."
                    ),
                },
                "blind_spot": {
                    "title": "Diya Iyer — overlooked long-tail discovery",
                    "investor_id": "DEMO-INV-L017",
                    "data": {
                        "snapshot": snap3,
                        "priority": pri3,
                        "summary": generate(snap3, pri3),
                    },
                    "why_overlooked": (
                        "Long-tail client with stale review, unresolved advice, and goal lag — "
                        "easy to miss in a CRM queue sorted by relationship tier."
                    ),
                },
                "is_demo": True,
            }
        )
    )


# ---------- Meeting Intelligence (Gemini-backed) ----------


@app.get("/api/meeting-intel/status")
def meeting_intel_status():
    return to_jsonable(meeting_intel.provider_status())


@app.get("/api/meeting-intel/meetings")
def meeting_intel_list(investor_id: str | None = None):
    return JSONResponse(to_jsonable(meeting_intel.list_meetings(investor_id)))


@app.post("/api/meeting-intel/meetings")
def meeting_intel_create(body: MeetingCreateIn):
    result = meeting_intel.create_meeting(store(), body.model_dump())
    if result.get("error"):
        raise HTTPException(404, result["error"])
    return JSONResponse(to_jsonable(result))


@app.get("/api/meeting-intel/meetings/{meeting_id}")
def meeting_intel_get(meeting_id: str):
    result = meeting_intel.get_meeting(meeting_id)
    if result.get("error"):
        raise HTTPException(404, result["error"])
    return JSONResponse(to_jsonable(result))


@app.patch("/api/meeting-intel/meetings/{meeting_id}")
def meeting_intel_patch(meeting_id: str, body: MeetingPatchIn):
    patch = {k: v for k, v in body.model_dump().items() if v is not None}
    result = meeting_intel.update_meeting(meeting_id, patch)
    if result.get("error"):
        raise HTTPException(404, result["error"])
    return JSONResponse(to_jsonable(result))


@app.post("/api/meeting-intel/meetings/{meeting_id}/prepare")
def meeting_intel_prepare(meeting_id: str, regenerate: bool = False):
    result = meeting_intel.build_preparation_brief(store(), meeting_id, regenerate=regenerate)
    if result.get("error"):
        raise HTTPException(400, result["error"])
    return JSONResponse(to_jsonable(result))


@app.post("/api/meeting-intel/meetings/{meeting_id}/consent")
def meeting_intel_consent(meeting_id: str, body: ConsentIn):
    result = meeting_intel.confirm_consent(meeting_id, body.note)
    if result.get("error"):
        raise HTTPException(404, result["error"])
    return JSONResponse(to_jsonable(result))


@app.post("/api/meeting-intel/meetings/{meeting_id}/start")
def meeting_intel_start(meeting_id: str):
    result = meeting_intel.start_session(meeting_id)
    if result.get("error"):
        raise HTTPException(400, result["error"])
    return JSONResponse(to_jsonable(result))


@app.post("/api/meeting-intel/meetings/{meeting_id}/recording-state")
def meeting_intel_rec_state(meeting_id: str, state: str):
    result = meeting_intel.set_recording_state(meeting_id, state)
    if result.get("error"):
        raise HTTPException(400, result["error"])
    return JSONResponse(to_jsonable(result))


@app.post("/api/meeting-intel/meetings/{meeting_id}/notes")
def meeting_intel_note(meeting_id: str, body: LiveNoteIn):
    result = meeting_intel.add_live_note(meeting_id, body.model_dump())
    if result.get("error"):
        raise HTTPException(404, result["error"])
    return JSONResponse(to_jsonable(result))


@app.post("/api/meeting-intel/meetings/{meeting_id}/upload-audio")
async def meeting_intel_upload(meeting_id: str, file: UploadFile = File(...)):
    content = await file.read()
    result = meeting_intel.save_recording_bytes(
        meeting_id, content, file.filename or "recording.webm", file.content_type
    )
    if result.get("error"):
        raise HTTPException(400, result["error"])
    return JSONResponse(to_jsonable(result))


@app.post("/api/meeting-intel/meetings/{meeting_id}/transcribe")
def meeting_intel_transcribe(meeting_id: str):
    result = meeting_intel.transcribe_meeting(meeting_id)
    if result.get("error"):
        raise HTTPException(400, result["error"])
    return JSONResponse(to_jsonable(result))


@app.post("/api/meeting-intel/meetings/{meeting_id}/transcript/paste")
def meeting_intel_transcript_paste(meeting_id: str, body: TranscriptPasteIn):
    result = meeting_intel.set_manual_transcript(meeting_id, body.text, body.segments)
    if result.get("error"):
        raise HTTPException(400, result["error"])
    return JSONResponse(to_jsonable(result))


@app.put("/api/meeting-intel/meetings/{meeting_id}/transcript")
def meeting_intel_transcript_update(meeting_id: str, body: TranscriptUpdateIn):
    result = meeting_intel.update_transcript(
        meeting_id, {k: v for k, v in body.model_dump().items() if v is not None}
    )
    if result.get("error"):
        raise HTTPException(404, result["error"])
    return JSONResponse(to_jsonable(result))


@app.post("/api/meeting-intel/meetings/{meeting_id}/minutes/generate")
def meeting_intel_minutes_gen(meeting_id: str):
    result = meeting_intel.generate_minutes(store(), meeting_id)
    if result.get("error"):
        raise HTTPException(400, result["error"])
    return JSONResponse(to_jsonable(result))


@app.patch("/api/meeting-intel/meetings/{meeting_id}/minutes")
def meeting_intel_minutes_patch(meeting_id: str, body: MinutesPatchIn):
    patch = {k: v for k, v in body.model_dump().items() if v is not None}
    result = meeting_intel.update_minutes(meeting_id, patch)
    if result.get("error"):
        raise HTTPException(404, result["error"])
    return JSONResponse(to_jsonable(result))


@app.post("/api/meeting-intel/meetings/{meeting_id}/minutes/approve")
def meeting_intel_minutes_approve(meeting_id: str):
    result = meeting_intel.approve_minutes(meeting_id)
    if result.get("error"):
        raise HTTPException(400, result["error"])
    return JSONResponse(to_jsonable(result))


@app.post("/api/meeting-intel/meetings/{meeting_id}/commitments")
def meeting_intel_commitments(meeting_id: str, body: CommitmentsFromActionsIn):
    result = meeting_intel.create_commitments_from_actions(meeting_id, body.action_ids)
    if result.get("error"):
        raise HTTPException(400, result["error"])
    return JSONResponse(to_jsonable(result))


@app.post("/api/meeting-intel/meetings/{meeting_id}/end")
def meeting_intel_end(meeting_id: str):
    result = meeting_intel.end_meeting(meeting_id)
    if result.get("error"):
        raise HTTPException(404, result["error"])
    return JSONResponse(to_jsonable(result))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
