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
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from services import google_meet

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
    attention_engine_page as attention_engine_svc,
    blind_spot,
    client_summary,
    copilot,
    drift,
    feedback,
    meeting_intel,
    market_shock,
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
    """Legacy per-client what-if (SIP/allocation). UI uses Market Shock; Copilot still may call SIP."""

    sip_delta: float = 0.0
    return_delta_pp: float = 0.0
    years_override: float | None = None
    lump_sum: float = 0.0
    scenario_type: str = "sip_contribution"
    proposed_weights: dict[str, float] | None = None
    market_shocks: dict[str, float] | None = None


class MarketShockIn(BaseModel):
    """Market & Asset Scenario request. Supports stock / index / broad_market with signed moves."""

    scenario_name: str | None = None
    scenario_type: str = "broad_market"  # stock | index | broad_market
    instrument_id: str | None = None
    price_change_pct: float | None = Field(default=None, ge=-30.0, le=30.0)
    # Legacy field — used when price_change_pct omitted
    equity_market_shock_pct: float | None = Field(default=None, ge=-30.0, le=30.0)
    include_indirect_exposure: bool = True
    assumptions_version: str = "demo-v1"
    preset_id: str | None = None
    include_goal_impact: bool = True
    advisor_id: str = "DEMO-ADV-USER-01"


class MarketShockReviewIn(BaseModel):
    investor_id: str
    scenario_equity_shock_pct: float = -12.0
    note: str = ""
    advisor_id: str = "DEMO-ADV-USER-01"


class CopilotIn(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    context_investor_id: str | None = None
    advisor_id: str = "DEMO-ADV-USER-01"
    conversation_context: dict[str, Any] | None = None


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
            "market_shock",
            "patterns",
            "meeting_prep",
            "evidence_guard",
            "feedback_loop",
            "blind_spot_radar",
            "attention_engine_page",
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


@app.get("/api/attention-engine")
def get_attention_engine():
    """
    Dedicated Attention Engine page payload.
    Reuses rank_book + blind_spot obscurity/segments — no second scoring model.
    """
    return JSONResponse(to_jsonable(attention_engine_svc.build_attention_engine(store())))


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
    """Legacy per-client what-if retained for Copilot SIP / tests. Active UI is Market Shock."""
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


@app.get("/api/market-shock/assumptions")
def market_shock_assumptions():
    return JSONResponse(to_jsonable(market_shock.assumptions_catalog()))


@app.get("/api/market-shock/instruments")
def market_shock_instruments(kind: str | None = None):
    return JSONResponse(
        to_jsonable(
            {
                "instruments": market_shock.list_instruments(kind),
                "is_demo": True,
            }
        )
    )


@app.post("/api/market-shock/run")
def market_shock_run(body: MarketShockIn):
    pct = body.price_change_pct
    if pct is None:
        pct = body.equity_market_shock_pct
    if pct is None:
        pct = -12.0
    result = market_shock.run_scenario(
        store(),
        scenario_type=body.scenario_type,
        instrument_id=body.instrument_id,
        price_change_pct=pct,
        include_indirect_exposure=body.include_indirect_exposure,
        assumptions_version=body.assumptions_version,
        advisor_id=body.advisor_id,
        scenario_name=body.scenario_name,
    )
    if result.get("error"):
        raise HTTPException(400, result["error"])
    return JSONResponse(to_jsonable(result))


@app.post("/api/market-shock/mark-reviewed")
def market_shock_mark_reviewed(body: MarketShockReviewIn):
    out = market_shock.mark_reviewed(
        body.investor_id,
        scenario_equity_shock_pct=body.scenario_equity_shock_pct,
        note=body.note,
        advisor_id=body.advisor_id,
    )
    if out.get("denied"):
        raise HTTPException(403, out.get("message") or "Access denied")
    return JSONResponse(to_jsonable(out))


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


@app.get("/api/copilot/demo-catalog")
def copilot_demo_catalog():
    """Seeded demo questions/scenarios — templates only; facts come from live analysis."""
    return JSONResponse(to_jsonable(copilot.demo_catalog()))


@app.post("/api/copilot")
def copilot_query(body: CopilotIn):
    return JSONResponse(
        to_jsonable(
            copilot.route_query(
                store(),
                body.query,
                context_investor_id=body.context_investor_id,
                advisor_id=body.advisor_id,
                conversation_context=body.conversation_context,
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


@app.post("/api/meeting-intel/meetings/{meeting_id}/schedule-meet")
def meeting_intel_schedule_meet(meeting_id: str, prefer_google: bool = True):
    result = meeting_intel.schedule_meet(meeting_id, prefer_google=prefer_google)
    if result.get("error") and not (result.get("meeting") or {}).get("meet_link"):
        raise HTTPException(400, result["error"])
    return JSONResponse(to_jsonable(result))


@app.post("/api/meeting-intel/meetings/{meeting_id}/load-demo-transcript")
def meeting_intel_load_demo_transcript(meeting_id: str):
    result = meeting_intel.load_demo_transcript(meeting_id, store=store())
    if result.get("error"):
        raise HTTPException(400, result["error"])
    return JSONResponse(to_jsonable(result))


@app.post("/api/meeting-intel/seed-demo")
def meeting_intel_seed_demo():
    """One-click Priya demo: prep + video room + packaged transcript."""
    result = meeting_intel.seed_demo_meeting(store())
    if result.get("error"):
        raise HTTPException(400, result["error"])
    return JSONResponse(to_jsonable(result))


@app.get("/api/meeting-intel/google/status")
def meeting_intel_google_status():
    return JSONResponse(to_jsonable(google_meet.status()))


@app.get("/api/meeting-intel/google/auth-url")
def meeting_intel_google_auth_url():
    result = google_meet.auth_url()
    if result.get("error"):
        raise HTTPException(400, result["error"])
    return JSONResponse(to_jsonable(result))


@app.get("/api/meeting-intel/google/callback")
def meeting_intel_google_callback(code: str | None = None, error: str | None = None):
    if error:
        return HTMLResponse(
            f"<html><body><h2>Google connect failed</h2><p>{error}</p>"
            "<p>Close this tab and retry from Meeting Intelligence.</p></body></html>",
            status_code=400,
        )
    if not code:
        raise HTTPException(400, "Missing OAuth code")
    result = google_meet.exchange_code(code)
    if result.get("error"):
        return HTMLResponse(
            f"<html><body><h2>Token exchange failed</h2><p>{result['error']}</p></body></html>",
            status_code=400,
        )
    # Prefer SPA route when frontend is mounted
    return HTMLResponse(
        "<html><body><h2>Google Calendar connected</h2>"
        "<p>You can close this tab and return to Meeting Intelligence. "
        "Create Meet will now use Google Meet when available.</p>"
        "<script>setTimeout(function(){ window.close(); }, 1500);</script>"
        "</body></html>"
    )


# ---------- Production SPA (frontend/dist) ----------

FRONTEND_DIST = ROOT / "frontend" / "dist"


def _mount_frontend() -> None:
    """Serve Vite build from the same origin as the API when dist/ exists."""
    if not FRONTEND_DIST.is_dir() or not (FRONTEND_DIST / "index.html").exists():
        return
    assets = FRONTEND_DIST / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="frontend_assets")

    @app.get("/")
    def spa_index():
        return FileResponse(FRONTEND_DIST / "index.html")

    @app.get("/{full_path:path}")
    def spa_fallback(full_path: str):
        if full_path.startswith("api/") or full_path == "api" or full_path.startswith("docs"):
            raise HTTPException(404, "Not found")
        candidate = FRONTEND_DIST / full_path
        if candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(FRONTEND_DIST / "index.html")


_mount_frontend()


if __name__ == "__main__":
    import os
    import uvicorn

    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("main:app", host=host, port=port, reload=False)
