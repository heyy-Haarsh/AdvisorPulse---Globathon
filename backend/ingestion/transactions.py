"""Layer 1 — transaction CSV ingestion and cash-flow signals only."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd


INVALID_DATE_TOKENS = {"########", "#", "nan", "none", "null", ""}

_CURRENCY_RE = re.compile(
    r"^\s*(?:INR|USD|EUR|GBP|₹|\$|€|£)?\s*([-]?)(?:₹|\$|€|£)?\s*([\d,]+(?:\.\d+)?)\s*$",
    re.IGNORECASE,
)


@dataclass
class IngestionReport:
    rows_read: int = 0
    rows_kept: int = 0
    duplicates_flagged: int = 0
    duplicates_dropped: int = 0  # legacy alias; we no longer auto-delete
    invalid_dates: int = 0
    invalid_amounts: int = 0
    currency_normalized: int = 0
    warnings: list[str] = field(default_factory=list)


def _normalize_type(v: Any) -> str:
    s = str(v or "").strip().lower()
    if s in {"credit", "cr", "inflow"}:
        return "credit"
    if s in {"debit", "dr", "outflow"}:
        return "debit"
    return s or "unknown"


def _suggest_category(description: str) -> str:
    d = (description or "").lower()
    if any(x in d for x in ("swiggy", "zomato", "food", "restaurant")):
        return "Food Delivery"
    if any(x in d for x in ("h&m", "myntra", "apparel", "clothing")):
        return "Clothing"
    if any(x in d for x in ("petrol", "fuel", "diesel")):
        return "Fuel"
    if any(x in d for x in ("salary", "payroll")):
        return "Income"
    if any(x in d for x in ("electric", "utility", "bill")):
        return "Utilities"
    return ""


def parse_amount(raw: Any) -> tuple[float | None, bool]:
    """
    Parse amounts with currency symbols and thousand separators.
    Returns (value, was_currency_normalized). Never returns 0 for missing/invalid.
    """
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return None, False
    s = str(raw).strip()
    if not s or s.lower() in {"nan", "none", "null", "abc", "#"}:
        return None, False
    m = _CURRENCY_RE.match(s)
    if not m:
        # try plain float
        try:
            return float(s.replace(",", "")), False
        except ValueError:
            return None, False
    sign, num = m.group(1), m.group(2)
    try:
        val = float(num.replace(",", ""))
    except ValueError:
        return None, False
    if sign == "-":
        val = -val
    normalized = bool(re.search(r"[₹$€£,]", s)) or bool(re.search(r"(INR|USD|EUR|GBP)", s, re.I))
    return val, normalized


def load_transactions(path: str | Path) -> tuple[pd.DataFrame, IngestionReport]:
    report = IngestionReport()
    path = Path(path)
    if not path.exists():
        report.warnings.append(f"Transaction file not found: {path}")
        return pd.DataFrame(), report

    df = pd.read_csv(path, dtype=str)
    report.rows_read = len(df)

    for col in df.columns:
        df[col] = df[col].astype(str).str.strip()

    # Flag duplicates — do NOT auto-delete
    # 1) same transaction_id  2) same content fingerprint (user/date/time/desc/amount)
    df["is_duplicate"] = False
    df["duplicate_reason"] = ""
    if "transaction_id" in df.columns:
        dup_mask = df.duplicated(subset=["transaction_id"], keep="first")
        df.loc[dup_mask, "is_duplicate"] = True
        df.loc[dup_mask, "duplicate_reason"] = "duplicate_transaction_id"
    content_cols = [c for c in ["user_id", "date", "time", "description", "amount"] if c in df.columns]
    if len(content_cols) >= 4:
        content_dup = df.duplicated(subset=content_cols, keep="first")
        # Flag content duplicates even if transaction_id differs
        new_content = content_dup & ~df["is_duplicate"]
        df.loc[new_content, "is_duplicate"] = True
        df.loc[new_content, "duplicate_reason"] = "probable_duplicate_same_content"
        df.loc[content_dup & (df["duplicate_reason"] == ""), "duplicate_reason"] = "duplicate_transaction_id"
    report.duplicates_flagged = int(df["is_duplicate"].sum())
    if report.duplicates_flagged:
        report.warnings.append(
            f"{report.duplicates_flagged} duplicate/probable-duplicate row(s) flagged — not auto-deleted."
        )
    report.duplicates_dropped = 0  # explicit: we do not drop

    # Dates — prefer DD-MM-YYYY (declared sample format), then ISO, then coerce
    if "date" in df.columns:
        bad = df["date"].str.lower().isin(INVALID_DATE_TOKENS) | df["date"].isna()
        report.invalid_dates = int(bad.sum())
        df.loc[bad, "date"] = pd.NA
        dmy = pd.to_datetime(df["date"], errors="coerce", format="%d-%m-%Y")
        iso = pd.to_datetime(df["date"], errors="coerce", format="%Y-%m-%d")
        # Prefer explicit formats first to avoid dayfirst warnings on ISO strings
        df["date_parsed"] = dmy.fillna(iso)
        still = df["date_parsed"].isna()
        if still.any():
            df.loc[still, "date_parsed"] = pd.to_datetime(
                df.loc[still, "date"], errors="coerce", dayfirst=True
            )
        unparsed = df["date"].notna() & df["date_parsed"].isna()
        report.invalid_dates = int((bad | unparsed).sum())
    else:
        df["date_parsed"] = pd.NaT
        report.warnings.append("Missing date column")

    # Amounts with currency / separators
    raw_amounts = df["amount"] if "amount" in df.columns else pd.Series([None] * len(df))
    parsed = [parse_amount(v) for v in raw_amounts]
    df["amount_raw"] = raw_amounts
    df["amount_num"] = [p[0] for p in parsed]
    report.currency_normalized = sum(1 for p in parsed if p[1])
    invalid_amt = df["amount_num"].isna()
    report.invalid_amounts = int(invalid_amt.sum())
    # Guard: never coerce missing to zero
    if (df.loc[invalid_amt, "amount_num"].fillna(0) == 0).any() and invalid_amt.any():
        # ensure NaN stays NaN (not 0)
        df.loc[invalid_amt, "amount_num"] = pd.NA

    if "category" in df.columns:
        df["category_raw"] = df["category"]
        df["category"] = df["category"].replace({"": "UNCATEGORIZED", "nan": "UNCATEGORIZED"})
        # Normalize common aliases before title-case
        cat_map = {
            "food_delivery": "Food Delivery",
            "food delivery": "Food Delivery",
            "fooddelivery": "Food Delivery",
        }
        df["category"] = df["category"].str.strip().str.lower().replace(cat_map)
        df["category"] = df["category"].str.title()
        df["category"] = df["category"].replace({"Uncategorized": "UNCATEGORIZED"})
        # Suggest category from description when missing
        df["category_suggested"] = ""
        missing_cat = df["category"].isin(["UNCATEGORIZED", ""])
        if "description" in df.columns:
            desc = df.loc[missing_cat, "description"].str.lower()
            sug = desc.map(_suggest_category)
            df.loc[missing_cat, "category_suggested"] = sug
    else:
        df["category"] = "UNCATEGORIZED"
        df["category_raw"] = ""
        df["category_suggested"] = ""

    if "city" in df.columns:
        df["city"] = df["city"].replace({"": "UNKNOWN", "nan": "UNKNOWN"})
        df["city"] = df["city"].str.title()
    else:
        df["city"] = "UNKNOWN"

    if "type" in df.columns:
        df["type_norm"] = df["type"].map(_normalize_type)
    else:
        df["type_norm"] = "unknown"

    if "currency" in df.columns:
        df["currency"] = df["currency"].str.upper().replace({"": "INR", "NAN": "INR"})
    else:
        df["currency"] = "INR"

    if "description" in df.columns:
        df["description"] = df["description"].str.replace(r"\s+", " ", regex=True)

    # Keep valid amounts; duplicates remain in the kept set (flagged)
    kept = df[~invalid_amt].copy()
    report.rows_kept = len(kept)
    return kept, report


def cashflow_signals(df: pd.DataFrame) -> dict[str, Any]:
    """Defensible cash-flow signals only — never investment suitability."""
    if df.empty:
        return {
            "available": False,
            "message": "No usable transaction rows after validation.",
            "limitations": ["Transaction file empty or missing."],
        }

    working = df[~df.get("is_duplicate", False)] if "is_duplicate" in df.columns else df
    credits = working[working["type_norm"] == "credit"]["amount_num"].sum()
    debits = working[working["type_norm"] == "debit"]["amount_num"].sum()
    by_cat = (
        working[working["type_norm"] == "debit"]
        .groupby("category")["amount_num"]
        .sum()
        .sort_values(ascending=False)
        .head(8)
        .to_dict()
    )

    recurring = []
    cred = working[working["type_norm"] == "credit"].copy()
    if not cred.empty and "date_parsed" in cred.columns:
        cred["ym"] = cred["date_parsed"].dt.to_period("M")
        for desc, g in cred.groupby("description"):
            months = g["ym"].nunique()
            if months >= 2 and pd.notna(desc):
                recurring.append(
                    {
                        "description": str(desc),
                        "months_observed": int(months),
                        "avg_amount": float(g["amount_num"].mean()),
                        "confidence": "medium" if months >= 3 else "low",
                    }
                )

    unusual = []
    deb = working[working["type_norm"] == "debit"]
    if len(deb) >= 10:
        med = deb["amount_num"].median()
        mad = (deb["amount_num"] - med).abs().median() or 1.0
        spikes = deb[deb["amount_num"] > med + 5 * mad].head(5)
        for _, r in spikes.iterrows():
            unusual.append(
                {
                    "transaction_id": r.get("transaction_id"),
                    "description": r.get("description"),
                    "amount": float(r["amount_num"]),
                    "reason": "Amount materially above typical debit level",
                    "confidence": "low",
                    "limitation": "Not evidence of investment risk or client dissatisfaction",
                }
            )

    dup_count = int(df["is_duplicate"].sum()) if "is_duplicate" in df.columns else 0

    return {
        "available": True,
        "currency": working["currency"].mode().iloc[0] if len(working) else "INR",
        "total_credits": float(credits),
        "total_debits": float(debits),
        "net_cashflow": float(credits - debits),
        "spend_by_category": {str(k): float(v) for k, v in by_cat.items()},
        "recurring_income_candidates": recurring[:5],
        "unusual_debits": unusual,
        "duplicates_flagged": dup_count,
        "limitations": [
            "Cash-flow signals only — not portfolio returns or risk tolerance.",
            "Merchant names alone do not imply investment suitability.",
            "Transaction data is never used as investment performance.",
        ],
    }
