"""Validate synthetic and sample data files."""
from __future__ import annotations

import csv
import sys
from pathlib import Path

DATA = Path(__file__).resolve().parent
REQUIRED = [
    "synthetic_investors.csv",
    "synthetic_goals.csv",
    "synthetic_holdings.csv",
    "synthetic_returns.csv",
    "synthetic_cashflows.csv",
    "synthetic_advice.csv",
    "synthetic_notes.csv",
]


def load(name: str) -> list[dict]:
    with (DATA / name).open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def main() -> int:
    errors: list[str] = []
    for name in REQUIRED:
        if not (DATA / name).exists():
            errors.append(f"Missing {name}")
    if errors:
        print("FAIL:", errors)
        return 1

    investors = load("synthetic_investors.csv")
    goals = load("synthetic_goals.csv")
    holdings = load("synthetic_holdings.csv")

    if len(investors) < 200:
        errors.append(f"Expected >=200 investors, got {len(investors)}")

    for row in investors:
        if row.get("is_demo", "").lower() != "true":
            errors.append(f"Investor {row.get('investor_id')} missing is_demo=true")
        if not str(row.get("investor_id", "")).startswith("DEMO-"):
            errors.append(f"Investor id not DEMO-prefixed: {row.get('investor_id')}")

    inv_ids = {r["investor_id"] for r in investors}
    for g in goals:
        if g["investor_id"] not in inv_ids:
            errors.append(f"Orphan goal {g['goal_id']}")
        if g.get("is_demo", "").lower() != "true":
            errors.append(f"Goal {g['goal_id']} not marked demo")

    for h in holdings:
        if h["investor_id"] not in inv_ids:
            errors.append(f"Orphan holding {h['holding_id']}")

    # Required narrative investors
    for need in ("DEMO-INV-001", "DEMO-INV-002"):
        if need not in inv_ids:
            errors.append(f"Missing narrative investor {need}")

    high = sum(1 for i in investors if i["tier"] == "high_visibility")
    if high < 18:
        errors.append(f"Expected ~20 high_visibility, got {high}")

    if errors:
        print("VALIDATION FAILED:")
        for e in errors[:30]:
            print(" -", e)
        print(f"... {len(errors)} total" if len(errors) > 30 else "")
        return 1

    print(f"OK: {len(investors)} investors, {len(goals)} goals, {len(holdings)} holdings")
    return 0


if __name__ == "__main__":
    sys.exit(main())
