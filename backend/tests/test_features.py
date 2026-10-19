"""Expanded suite for Advisor Pulse differentiating features."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from analytics.portfolio import DataStore  # noqa: E402
from domain.persistence import (  # noqa: E402
    RUNTIME,
    add_feedback,
    load_feedback,
    save_decision,
    save_settings,
)
from ingestion.transactions import load_transactions, parse_amount  # noqa: E402
from prioritization.engine import score_investor, rank_book  # noqa: E402
from services.advice_outcome import advice_outcome_report, evaluate_advice_item  # noqa: E402
from services.copilot import route_query  # noqa: E402
from services.memory import confirm_extraction, extract_from_text, mock_transcribe  # noqa: E402
from services.whatif import reproduce_hash_inputs, simulate  # noqa: E402
from services.feedback import record_feedback, timeline  # noqa: E402
from services.drift import detect_drift  # noqa: E402
from domain.persistence import load_settings  # noqa: E402


@pytest.fixture(scope="module")
def store():
    return DataStore.load()


def test_currency_parsing():
    assert parse_amount("₹1,25,000")[0] == 125000.0
    assert parse_amount("$1,250.50")[0] == 1250.50
    assert parse_amount("INR 85000")[0] == 85000.0
    assert parse_amount("abc")[0] is None
    assert parse_amount(None)[0] is None
    # Never silent zero from missing
    val, _ = parse_amount("")
    assert val is None


def test_duplicate_flagging(tmp_path):
    csv = tmp_path / "txn.csv"
    csv.write_text(
        "transaction_id,user_id,date,description,category,amount,currency,type,payment_mode,city\n"
        "TXN-1,u,2026-01-01,A,Income,100,INR,CREDIT,,\n"
        "TXN-1,u,2026-01-01,A,Income,100,INR,CREDIT,,\n"
        "TXN-2,u,########,B,Food,₹50,INR,DEBIT,,\n"
        "TXN-3,u,2026-01-02,C,Food,abc,INR,DEBIT,,\n",
        encoding="utf-8",
    )
    df, report = load_transactions(csv)
    assert report.duplicates_flagged == 1
    assert report.duplicates_dropped == 0
    assert "is_duplicate" in df.columns
    assert int(df["is_duplicate"].sum()) == 1
    assert report.invalid_amounts >= 1
    # invalid amount not coerced to zero in kept rows
    assert df[df["transaction_id"] == "TXN-3"].empty or df.loc[df["transaction_id"] == "TXN-3", "amount_num"].isna().all()


def test_no_silent_zero_missing_active(store):
    pri = score_investor(store, "DEMO-INV-001")
    # factor always present; missing returns would be points 0 with explicit detail
    names = [f["name"] for f in pri["factors"]]
    assert "active_underperformance" in names
    assert pri["confidence"] in {"Verified", "Limited", "Insufficient"}
    assert pri["severity"] in {"critical", "high", "medium", "low", "info"}
    # severity vs confidence are separate fields
    assert "confidence" in pri and "severity" in pri


def test_deterministic_priority(store):
    a = score_investor(store, "DEMO-INV-001")
    b = score_investor(store, "DEMO-INV-001")
    assert a["score"] == b["score"]
    assert a["priority"] == b["priority"]
    assert a["factors"] == b["factors"]


def test_explainable_alerts(store):
    pri = score_investor(store, "DEMO-INV-001")
    assert pri["evidence"]["evidence"]
    assert pri["priority_reason"]
    assert all("detail" in f for f in pri["factors"])


def test_attention_decision_demotes(store):
    save_decision("DEMO-INV-H03", {"investor_id": "DEMO-INV-H03", "action": "dismiss"})
    ranked = rank_book(store, include_resolved=True)
    row = next(r for r in ranked if r["investor_id"] == "DEMO-INV-H03")
    assert row["resolved"] is True
    assert row["queue_score"] < row["score"] or row["score"] == 0


def test_advice_outcome_and_insufficient(store):
    report = advice_outcome_report(store, "DEMO-INV-001")
    assert report["items"]
    assert report["counts"]["total"] >= 1
    # empty investor-like: use a known id with advice
    item = report["items"][0]
    assert "outcome_status" in item
    assert item["evidence"]["confidence"] in {"Verified", "Limited", "Insufficient"}
    assert item.get("immutable_note")


def test_insufficient_data_path(store):
    # Craft advice with no matching holdings pattern for generic eval still works
    fake = {
        "advice_id": "TEST-ADV-X",
        "recommendation": "Obscure custom mandate with no data hooks",
        "intended_outcome": "Unknown",
        "advice_date": "2026-01-01",
        "follow_up_status": "pending",
    }
    # Use investor with goals so not completely empty
    result = evaluate_advice_item(store, "DEMO-INV-001", fake)
    assert result["outcome_status"]
    assert result["evidence"]["confidence"] in {"Verified", "Limited", "Insufficient"}


def test_whatif_reproducible(store):
    a = simulate(store, "DEMO-INV-001", sip_delta=10000, return_delta_pp=0)
    b = simulate(store, "DEMO-INV-001", sip_delta=10000, return_delta_pp=0)
    assert a["is_hypothetical"] is True
    assert a["label"]
    assert a["assumptions"]
    assert a["formula"]
    assert reproduce_hash_inputs(a) == reproduce_hash_inputs(b)
    assert a["alternative"]["projected_value"] > a["baseline"]["projected_value"]


def test_copilot_access_control(store):
    # Restrict access via settings
    save_settings({"accessible_clients": ["DEMO-INV-001"]})
    denied = route_query(store, "summary for DEMO-INV-002", context_investor_id=None)
    assert denied.get("denied") is True
    allowed = route_query(store, "Why is DEMO-INV-001 critical?")
    assert allowed.get("denied") is not True
    assert allowed["mapped_function"]
    assert allowed["no_arbitrary_sql"] is True
    # restore open access
    save_settings({"accessible_clients": None})
    settings = load_settings()
    # None means all — persistence may store null
    assert settings.get("accessible_clients") in (None, [])


def test_note_confirmation_flow():
    # clean-ish: create extraction and confirm
    result = mock_transcribe("DEMO-INV-001", "Client agreed to rebalancing and SIP follow up by next month.")
    assert result["processing_mode"] == "mocked_local"
    ext = result["extraction"]
    assert ext["status"] == "pending_confirmation"
    assert ext["authoritative"] is False
    confirmed = confirm_extraction(ext["extraction_id"], create_followup=True)
    assert confirmed["extraction"]["authoritative"] is True
    assert confirmed["extraction"]["status"] == "confirmed"
    assert confirmed["attention_followup"] is not None


def test_feedback_persistence(store):
    before = len(load_feedback())
    record_feedback("DEMO-INV-001", "DEMO-ADV-001-A", "confirm", note="looks right")
    after = load_feedback()
    assert len(after) == before + 1
    assert after[-1]["action"] == "confirm"
    tl = timeline(store, "DEMO-INV-001")
    assert any(e["type"] == "advisor_feedback" for e in tl["events"])
    assert "caus" in tl["improvement_note"].lower() or "NOT" in tl["improvement_note"]


def test_drift_missing_not_distress(store):
    report = detect_drift(store, "DEMO-INV-001")
    assert "alerts" in report
    for a in report["alerts"]:
        if a["rule"] in {"stale_or_missing_valuation", "missing_holdings"}:
            assert a["is_distress"] is False
