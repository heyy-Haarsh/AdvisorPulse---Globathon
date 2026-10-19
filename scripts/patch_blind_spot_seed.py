"""Patch DEMO-INV-L017 as overlooked long-tail blind-spot hero."""
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"


def patch_csv(name: str, mutator) -> None:
    path = DATA / name
    rows = list(csv.DictReader(path.open(encoding="utf-8")))
    fields = list(rows[0].keys())
    for r in rows:
        mutator(r)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def main() -> None:
    def inv(r):
        if r["investor_id"] == "DEMO-INV-L017":
            r["last_review_date"] = "2025-08-10"
            r["notes_summary"] = "DEMO: Blind-spot overlooked long-tail — stale review + goal lag"

    def goal(r):
        if r["investor_id"] == "DEMO-INV-L017":
            r["status_hint"] = "critical_behind"
            r["target_amount"] = "6500000.00"
            r["goal_name"] = "Child education"

    def advice(r):
        if r["investor_id"] == "DEMO-INV-L017" and r["advice_id"].endswith("-0"):
            r["follow_up_status"] = "overdue"
            r["follow_up_due"] = "2026-01-15"
            r["recommendation"] = "Increase SIP and review equity drift for education goal"

    patch_csv("synthetic_investors.csv", inv)
    patch_csv("synthetic_goals.csv", goal)
    patch_csv("synthetic_advice.csv", advice)
    print("Patched DEMO-INV-L017 blind-spot seed")


if __name__ == "__main__":
    main()
