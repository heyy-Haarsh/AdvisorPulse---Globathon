"""
Transaction Data Quality pipeline:
Upload → Validate → Normalize → Flag → Review exceptions → Import → Refresh signals.
Layer-1 only — never joined silently to DEMO-INV portfolio records.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any
from uuid import uuid4

import pandas as pd

from domain.persistence import RUNTIME, _write, _read, audit
from ingestion.transactions import cashflow_signals, load_transactions

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
STAGING = RUNTIME / "txn_staging.csv"
IMPORTED = RUNTIME / "imported_transactions.csv"
EXCEPTIONS_FILE = "txn_exceptions.json"


def quality_summary(df: pd.DataFrame, report) -> dict[str, Any]:
    missing_cat = int((df.get("category", pd.Series(dtype=str)) == "UNCATEGORIZED").sum()) if len(df) else 0
    missing_city = int((df.get("city", pd.Series(dtype=str)) == "UNKNOWN").sum()) if len(df) else 0
    suggested = int((df.get("category_suggested", pd.Series(dtype=str)).fillna("") != "").sum()) if "category_suggested" in df.columns else 0
    return {
        "rows_read": report.rows_read,
        "rows_kept": report.rows_kept,
        "duplicates_flagged": report.duplicates_flagged,
        "invalid_dates": report.invalid_dates,
        "invalid_amounts": report.invalid_amounts,
        "currency_normalized": report.currency_normalized,
        "missing_category": missing_cat,
        "missing_city": missing_city,
        "category_suggestions": suggested,
        "warnings": report.warnings,
        "limitations": [
            "Cash-flow layer only — not portfolio returns.",
            "user_id values are not linked to DEMO-INV-* portfolio investors.",
            "Too few rows to establish spending baselines or financial distress.",
        ],
        "identity_note": "No silent join from transaction user_id to DEMO-INV-* portfolio records.",
    }


def build_exceptions(df: pd.DataFrame) -> list[dict[str, Any]]:
    exceptions: list[dict[str, Any]] = []
    if df.empty:
        return exceptions
    for idx, r in df.iterrows():
        reasons = []
        if r.get("is_duplicate"):
            reasons.append(r.get("duplicate_reason") or "duplicate")
        if r.get("category") == "UNCATEGORIZED":
            reasons.append("missing_category")
        if r.get("city") == "UNKNOWN":
            reasons.append("missing_city")
        if pd.isna(r.get("date_parsed")):
            reasons.append("invalid_or_missing_date")
        if not reasons:
            continue
        exceptions.append(
            {
                "exception_id": f"TXN-EX-{idx}-{uuid4().hex[:6]}",
                "transaction_id": r.get("transaction_id"),
                "user_id": r.get("user_id"),
                "description": r.get("description"),
                "amount_raw": r.get("amount_raw"),
                "amount_num": None if pd.isna(r.get("amount_num")) else float(r.get("amount_num")),
                "category": r.get("category"),
                "category_suggested": r.get("category_suggested") or "",
                "city": r.get("city"),
                "reasons": reasons,
                "status": "open",
            }
        )
    return exceptions


def validate_bytes(content: bytes, filename: str = "upload.csv") -> dict[str, Any]:
    staging = RUNTIME / f"upload_{uuid4().hex[:8]}.csv"
    staging.write_bytes(content)
    df, report = load_transactions(staging)
    # Persist staging for import
    if not df.empty:
        df.to_csv(STAGING, index=False)
    else:
        # still copy raw for inspection
        shutil.copy(staging, STAGING)
    exceptions = build_exceptions(df)
    _write(EXCEPTIONS_FILE, exceptions)
    audit("txn_validate", {"filename": filename, "rows_read": report.rows_read})
    summary = quality_summary(df, report)
    summary["filename"] = filename
    summary["staging_path"] = str(STAGING)
    summary["exception_count"] = len(exceptions)
    summary["signals_preview"] = cashflow_signals(df)
    return {"summary": summary, "exceptions": exceptions[:50], "is_demo": True}


def validate_path(path: Path) -> dict[str, Any]:
    content = path.read_bytes()
    return validate_bytes(content, path.name)


def list_exceptions() -> list[dict[str, Any]]:
    return _read(EXCEPTIONS_FILE, [])


def resolve_exception(exception_id: str, resolution: str, note: str = "") -> dict[str, Any]:
    items = list_exceptions()
    for item in items:
        if item.get("exception_id") == exception_id:
            item["status"] = resolution  # confirm_duplicate | ignore | apply_suggestion | dismiss
            item["note"] = note
            _write(EXCEPTIONS_FILE, items)
            audit("txn_exception_resolve", {"exception_id": exception_id, "resolution": resolution})
            return item
    raise KeyError(exception_id)


def import_staged() -> dict[str, Any]:
    if not STAGING.exists():
        raise FileNotFoundError("No staged CSV — validate/upload first")
    shutil.copy(STAGING, IMPORTED)
    df, report = load_transactions(IMPORTED)
    audit("txn_import", {"rows_kept": report.rows_kept})
    return {
        "imported_path": str(IMPORTED),
        "summary": quality_summary(df, report),
        "signals": cashflow_signals(df),
        "is_demo": True,
    }


def active_signals() -> dict[str, Any]:
    path = IMPORTED if IMPORTED.exists() else DATA / "sample_transactions.csv"
    df, report = load_transactions(path)
    return {
        "source": str(path),
        "ingestion_report": report.__dict__,
        "signals": cashflow_signals(df),
        "summary": quality_summary(df, report),
        "layer": 1,
        "is_demo": True,
    }
