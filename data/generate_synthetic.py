"""
Generate clearly labeled DEMO / SYNTHETIC portfolio data for Advisor Pulse.
All investor IDs use DEMO- prefix. is_demo is always true.
"""
from __future__ import annotations

import csv
import math
import random
from datetime import date, datetime, timedelta
from pathlib import Path

SEED = 42
OUT = Path(__file__).resolve().parent
TODAY = date(2026, 10, 17)
random.seed(SEED)

ASSET_CLASSES = [
    ("Equity - Large Cap", 0.35),
    ("Equity - Mid Cap", 0.15),
    ("Debt - Duration", 0.25),
    ("Hybrid / Balanced", 0.15),
    ("Cash / Liquid", 0.10),
]

BENCHMARKS = {
    "Moderate": "NIFTY_50_TRI_PROXY_DEMO",
    "Aggressive": "NIFTY_500_TRI_PROXY_DEMO",
    "Conservative": "CRISIL_COMPOSITE_BOND_PROXY_DEMO",
}

FIRST = [
    "Aarav", "Vivaan", "Aditya", "Vihaan", "Arjun", "Sai", "Reyansh", "Ayaan",
    "Krishna", "Ishaan", "Shaurya", "Atharv", "Kabir", "Ananya", "Aadhya",
    "Diya", "Myra", "Sara", "Anika", "Ira", "Aarohi", "Pari", "Riya", "Navya",
    "Priya", "Neha", "Rohan", "Karan", "Meera", "Sneha", "Rahul", "Pooja",
]
LAST = [
    "Sharma", "Patel", "Mehta", "Singh", "Gupta", "Iyer", "Nair", "Reddy",
    "Kulkarni", "Joshi", "Desai", "Chopra", "Kapoor", "Malhotra", "Banerjee",
    "Chatterjee", "Pillai", "Rao", "Verma", "Shah",
]


def money(x: float) -> str:
    return f"{x:.2f}"


def write_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)
    print(f"Wrote {path.name}: {len(rows)} rows")


def build_investors() -> list[dict]:
    rows: list[dict] = []

    # Primary story: Priya Sharma — falling behind retirement goal
    rows.append(
        {
            "investor_id": "DEMO-INV-001",
            "display_name": "Priya Sharma",
            "is_demo": "true",
            "tier": "high_visibility",
            "risk_profile": "Moderate",
            "age": "42",
            "city": "Pune",
            "currency": "INR",
            "aum_band": "50L-1Cr",
            "last_review_date": (TODAY - timedelta(days=95)).isoformat(),
            "data_freshness_days": "3",
            "visibility_rank": "3",
            "notes_summary": "DEMO: Core walkthrough investor with goal deviation",
        }
    )
    # Contrasting case: looks concerning absolute, explained by withdrawal
    rows.append(
        {
            "investor_id": "DEMO-INV-002",
            "display_name": "Arjun Mehta",
            "is_demo": "true",
            "tier": "high_visibility",
            "risk_profile": "Aggressive",
            "age": "38",
            "city": "Mumbai",
            "currency": "INR",
            "aum_band": "1Cr-2Cr",
            "last_review_date": (TODAY - timedelta(days=28)).isoformat(),
            "data_freshness_days": "2",
            "visibility_rank": "5",
            "notes_summary": "DEMO: Contrasting case — planned withdrawal explains gap",
        }
    )

    # High-visibility H01-H20 (include 001/002 slots conceptually as known)
    for i in range(1, 21):
        if i <= 2:
            continue  # already have primary demos as high-vis
        rid = f"DEMO-INV-H{i:02d}"
        name = f"{random.choice(FIRST)} {random.choice(LAST)}"
        risk = random.choice(["Conservative", "Moderate", "Aggressive"])
        rows.append(
            {
                "investor_id": rid,
                "display_name": name,
                "is_demo": "true",
                "tier": "high_visibility",
                "risk_profile": risk,
                "age": str(random.randint(32, 62)),
                "city": random.choice(["Pune", "Mumbai", "Bengaluru", "Delhi", "Hyderabad"]),
                "currency": "INR",
                "aum_band": random.choice(["50L-1Cr", "1Cr-2Cr", "2Cr+"]),
                "last_review_date": (TODAY - timedelta(days=random.randint(7, 60))).isoformat(),
                "data_freshness_days": str(random.randint(1, 10)),
                "visibility_rank": str(i),
                "notes_summary": "DEMO: high-visibility client",
            }
        )

    # Long-tail L001-L200
    for i in range(1, 201):
        rid = f"DEMO-INV-L{i:03d}"
        name = f"{random.choice(FIRST)} {random.choice(LAST)}"
        risk = random.choice(["Conservative", "Moderate", "Aggressive"])
        # Some stale reviews / stale data for prioritization signals
        stale = i % 17 == 0
        missing_val = i % 29 == 0
        rows.append(
            {
                "investor_id": rid,
                "display_name": name,
                "is_demo": "true",
                "tier": "long_tail",
                "risk_profile": risk,
                "age": str(random.randint(28, 68)),
                "city": random.choice(["Pune", "Mumbai", "Bengaluru", "Delhi", "Chennai", "Kolhapur"]),
                "currency": "INR",
                "aum_band": random.choice(["<25L", "25L-50L", "50L-1Cr"]),
                "last_review_date": (
                    (TODAY - timedelta(days=random.randint(120, 400))).isoformat()
                    if stale
                    else (TODAY - timedelta(days=random.randint(20, 150))).isoformat()
                ),
                "data_freshness_days": "999" if missing_val else str(random.randint(1, 45)),
                "visibility_rank": "",
                "notes_summary": "DEMO: long-tail client",
            }
        )
    return rows


def build_goals(investors: list[dict]) -> list[dict]:
    goals = []
    for inv in investors:
        iid = inv["investor_id"]
        risk = inv["risk_profile"]
        years = random.randint(5, 20)
        target_date = TODAY + timedelta(days=365 * years)
        # Base AUM proxy by band
        band = inv["aum_band"]
        current = {
            "<25L": 1_200_000,
            "25L-50L": 3_500_000,
            "50L-1Cr": 7_500_000,
            "1Cr-2Cr": 14_000_000,
            "2Cr+": 28_000_000,
        }.get(band, 5_000_000)
        # deterministic jitter
        jitter = (hash(iid) % 1000) / 1000.0
        current = current * (0.85 + 0.3 * jitter)

        if iid == "DEMO-INV-001":
            goals.append(
                {
                    "goal_id": "DEMO-GOAL-001",
                    "investor_id": iid,
                    "is_demo": "true",
                    "goal_name": "Retirement corpus",
                    "goal_type": "retirement",
                    "target_amount": money(25_000_000),
                    "current_mapped_value": money(7_200_000),
                    "target_date": "2038-03-31",
                    "start_date": "2019-04-01",
                    "expected_annual_return_pct": "9.0",
                    "required_monthly_sip": money(45000),
                    "currency": "INR",
                    "status_hint": "behind",
                    "benchmark_id": BENCHMARKS["Moderate"],
                }
            )
            continue
        if iid == "DEMO-INV-002":
            goals.append(
                {
                    "goal_id": "DEMO-GOAL-002",
                    "investor_id": iid,
                    "is_demo": "true",
                    "goal_name": "Child education",
                    "goal_type": "education",
                    "target_amount": money(12_000_000),
                    "current_mapped_value": money(11_400_000),
                    "target_date": "2030-06-30",
                    "start_date": "2018-01-15",
                    "expected_annual_return_pct": "10.5",
                    "required_monthly_sip": money(30000),
                    "currency": "INR",
                    "status_hint": "on_track_after_withdrawal",
                    "benchmark_id": BENCHMARKS["Aggressive"],
                }
            )
            continue

        expected = {"Conservative": 7.0, "Moderate": 9.0, "Aggressive": 11.0}[risk]
        # Mix of statuses
        roll = (hash(iid) % 10)
        if roll <= 1:
            hint = "critical_behind"
            current_v = current * 0.72
        elif roll <= 3:
            hint = "behind"
            current_v = current * 0.88
        elif roll == 4:
            hint = "data_stale"
            current_v = current
        else:
            hint = "on_track"
            current_v = current * (1.0 + 0.05 * ((hash(iid) % 5) - 2) / 5)

        target = current_v * ((1 + expected / 100) ** years) * 1.15
        goals.append(
            {
                "goal_id": f"DEMO-GOAL-{iid.split('-')[-1]}",
                "investor_id": iid,
                "is_demo": "true",
                "goal_name": random.choice(
                    ["Retirement corpus", "Home down payment", "Child education", "Wealth accumulation"]
                ),
                "goal_type": random.choice(["retirement", "home", "education", "wealth"]),
                "target_amount": money(target),
                "current_mapped_value": money(current_v),
                "target_date": target_date.isoformat(),
                "start_date": (TODAY - timedelta(days=365 * random.randint(2, 8))).isoformat(),
                "expected_annual_return_pct": str(expected),
                "required_monthly_sip": money(current_v * 0.006),
                "currency": "INR",
                "status_hint": hint,
                "benchmark_id": BENCHMARKS[risk],
            }
        )
    return goals


def build_holdings(investors: list[dict], goals: list[dict]) -> list[dict]:
    goal_map = {g["investor_id"]: g for g in goals}
    rows = []
    instruments = {
        "Equity - Large Cap": ["DEMO-ETF-NIFTYBEES", "DEMO-MF-LARGECAP-A", "DEMO-STOCK-RELIANCE_PROXY"],
        "Equity - Mid Cap": ["DEMO-MF-MIDCAP-B", "DEMO-ETF-MID150"],
        "Debt - Duration": ["DEMO-MF-DEBT-GILT", "DEMO-MF-CORP-BOND"],
        "Hybrid / Balanced": ["DEMO-MF-HYBRID-C"],
        "Cash / Liquid": ["DEMO-LIQUID-FUND", "DEMO-SAVINGS_PROXY"],
    }
    for inv in investors:
        iid = inv["investor_id"]
        g = goal_map[iid]
        total = float(g["current_mapped_value"])
        if iid == "DEMO-INV-001":
            # Equity overweight vs moderate plan — driver for gap story
            weights = [0.48, 0.22, 0.12, 0.10, 0.08]
        elif iid == "DEMO-INV-002":
            weights = [0.40, 0.25, 0.10, 0.15, 0.10]
        else:
            base = [w for _, w in ASSET_CLASSES]
            # small shuffle
            noise = [(hash(iid + ac) % 20 - 10) / 200 for ac, _ in ASSET_CLASSES]
            weights = [max(0.05, b + n) for b, n in zip(base, noise)]
            s = sum(weights)
            weights = [w / s for w in weights]

        for (ac, _), w in zip(ASSET_CLASSES, weights):
            mv = total * w
            qty = round(mv / random.uniform(80, 2500), 3)
            rows.append(
                {
                    "holding_id": f"DEMO-HLD-{iid.split('-')[-1]}-{ac[:3].upper()}",
                    "investor_id": iid,
                    "is_demo": "true",
                    "instrument_id": random.choice(instruments[ac]),
                    "instrument_name": f"{ac} sleeve (DEMO)",
                    "asset_class": ac,
                    "quantity": f"{qty:.3f}",
                    "market_value": money(mv),
                    "currency": "INR",
                    "as_of_date": (TODAY - timedelta(days=int(inv["data_freshness_days"]) if inv["data_freshness_days"] != "999" else 60)).isoformat(),
                    "weight_pct": f"{w * 100:.2f}",
                }
            )
    return rows


def build_returns(investors: list[dict], goals: list[dict]) -> list[dict]:
    goal_map = {g["investor_id"]: g for g in goals}
    rows = []
    months = 18
    for inv in investors:
        iid = inv["investor_id"]
        g = goal_map[iid]
        bench = g["benchmark_id"]
        expected_m = float(g["expected_annual_return_pct"]) / 100 / 12
        # Series of monthly returns
        port_val = float(g["current_mapped_value"]) / 1.08  # back out roughly
        for m in range(months, 0, -1):
            d = (TODAY.replace(day=1) - timedelta(days=30 * m))
            period = d.strftime("%Y-%m")
            # market factor
            market = expected_m + random.uniform(-0.025, 0.025)
            if iid == "DEMO-INV-001":
                # underperform last 9 months due to midcap drag + cash drag earlier
                if m <= 9:
                    port_r = market - 0.012 - (0.004 if m <= 4 else 0)
                else:
                    port_r = market + 0.002
            elif iid == "DEMO-INV-002":
                # solid investment returns; absolute value dip from withdrawal handled in cashflows
                port_r = market + 0.003
            else:
                hint = g["status_hint"]
                if hint == "critical_behind":
                    port_r = market - 0.015
                elif hint == "behind":
                    port_r = market - 0.008
                else:
                    port_r = market + random.uniform(-0.004, 0.006)

            port_val = port_val * (1 + port_r)
            rows.append(
                {
                    "investor_id": iid,
                    "is_demo": "true",
                    "period": period,
                    "period_end_date": (d.replace(day=28)).isoformat(),
                    "portfolio_return_pct": f"{port_r * 100:.4f}",
                    "benchmark_id": bench,
                    "benchmark_return_pct": f"{market * 100:.4f}",
                    "portfolio_value_eom": money(port_val),
                    "methodology_note": "DEMO monthly simple period return; TWR used in engine when cashflows present",
                }
            )
    return rows


def build_cashflows(investors: list[dict]) -> list[dict]:
    rows = []
    for inv in investors:
        iid = inv["investor_id"]
        # monthly SIP
        sip = 25000 + (hash(iid) % 40) * 1000
        if iid == "DEMO-INV-001":
            sip = 45000
        if iid == "DEMO-INV-002":
            sip = 30000
        for m in range(1, 13):
            d = TODAY.replace(day=5) - timedelta(days=30 * m)
            rows.append(
                {
                    "cashflow_id": f"DEMO-CF-{iid.split('-')[-1]}-SIP-{m}",
                    "investor_id": iid,
                    "is_demo": "true",
                    "date": d.isoformat(),
                    "amount": money(sip),
                    "flow_type": "contribution",
                    "currency": "INR",
                    "note": "DEMO recurring SIP",
                }
            )
        if iid == "DEMO-INV-002":
            rows.append(
                {
                    "cashflow_id": "DEMO-CF-002-WD-1",
                    "investor_id": iid,
                    "is_demo": "true",
                    "date": (TODAY - timedelta(days=40)).isoformat(),
                    "amount": money(-1_800_000),
                    "flow_type": "withdrawal",
                    "currency": "INR",
                    "note": "DEMO planned education fee withdrawal — explains absolute value dip",
                }
            )
        # occasional withdrawal for some long-tail
        if "L" in iid and (hash(iid) % 23 == 0):
            rows.append(
                {
                    "cashflow_id": f"DEMO-CF-{iid.split('-')[-1]}-WD",
                    "investor_id": iid,
                    "is_demo": "true",
                    "date": (TODAY - timedelta(days=random.randint(20, 90))).isoformat(),
                    "amount": money(-random.randint(50_000, 400_000)),
                    "flow_type": "withdrawal",
                    "currency": "INR",
                    "note": "DEMO ad-hoc withdrawal",
                }
            )
    return rows


def build_advice(investors: list[dict]) -> list[dict]:
    rows = []
    templates = [
        ("Increase SIP by 10%", "pending", "Improve goal trajectory"),
        ("Rebalance to target allocation", "done", "Reduce equity drift"),
        ("Review emergency fund", "pending", "Liquidity buffer"),
        ("Tax-loss harvest candidates", "cancelled", "Seasonal review"),
        ("Consolidate overlapping funds", "pending", "Simplify portfolio"),
    ]
    for inv in investors:
        iid = inv["investor_id"]
        n = 2 if inv["tier"] == "long_tail" else 3
        if iid == "DEMO-INV-001":
            rows.append(
                {
                    "advice_id": "DEMO-ADV-001-A",
                    "investor_id": iid,
                    "is_demo": "true",
                    "advice_date": (TODAY - timedelta(days=120)).isoformat(),
                    "recommendation": "Reduce mid-cap overweight and restore debt sleeve to 25%",
                    "intended_outcome": "Lower tracking error vs moderate policy; improve goal path confidence",
                    "follow_up_status": "overdue",
                    "follow_up_due": (TODAY - timedelta(days=30)).isoformat(),
                    "advisor_id": "DEMO-ADV-USER-01",
                }
            )
            rows.append(
                {
                    "advice_id": "DEMO-ADV-001-B",
                    "investor_id": iid,
                    "is_demo": "true",
                    "advice_date": (TODAY - timedelta(days=300)).isoformat(),
                    "recommendation": "Raise monthly SIP from 35k to 45k",
                    "intended_outcome": "Close retirement funding gap",
                    "follow_up_status": "done",
                    "follow_up_due": (TODAY - timedelta(days=240)).isoformat(),
                    "advisor_id": "DEMO-ADV-USER-01",
                }
            )
            continue
        if iid == "DEMO-INV-002":
            rows.append(
                {
                    "advice_id": "DEMO-ADV-002-A",
                    "investor_id": iid,
                    "is_demo": "true",
                    "advice_date": (TODAY - timedelta(days=50)).isoformat(),
                    "recommendation": "Execute planned education withdrawal from liquid sleeve first",
                    "intended_outcome": "Fund fees without disrupting equity compounding",
                    "follow_up_status": "done",
                    "follow_up_due": (TODAY - timedelta(days=35)).isoformat(),
                    "advisor_id": "DEMO-ADV-USER-01",
                }
            )
            continue
        for j in range(n):
            rec, status, outcome = templates[(hash(iid) + j) % len(templates)]
            if inv["data_freshness_days"] == "999" and j == 0:
                status = "pending"
            rows.append(
                {
                    "advice_id": f"DEMO-ADV-{iid.split('-')[-1]}-{j}",
                    "investor_id": iid,
                    "is_demo": "true",
                    "advice_date": (TODAY - timedelta(days=30 * (j + 2) + (hash(iid) % 20))).isoformat(),
                    "recommendation": rec,
                    "intended_outcome": outcome,
                    "follow_up_status": status if not (status == "pending" and (hash(iid) % 11 == 0)) else "overdue",
                    "follow_up_due": (TODAY - timedelta(days=random.randint(-20, 60))).isoformat(),
                    "advisor_id": "DEMO-ADV-USER-01",
                }
            )
    return rows


def build_notes(investors: list[dict]) -> list[dict]:
    rows = []
    for inv in investors:
        iid = inv["investor_id"]
        if iid == "DEMO-INV-001":
            rows.append(
                {
                    "note_id": "DEMO-NOTE-001-1",
                    "investor_id": iid,
                    "is_demo": "true",
                    "created_at": (datetime.combine(TODAY - timedelta(days=95), datetime.min.time())).isoformat(),
                    "author": "DEMO-ADV-USER-01",
                    "note_text": "Client concerned about mid-cap volatility; agreed to review allocation in next quarter. DEMO DATA.",
                    "source": "manual",
                    "transcript_local": "false",
                }
            )
            continue
        if iid == "DEMO-INV-002":
            rows.append(
                {
                    "note_id": "DEMO-NOTE-002-1",
                    "investor_id": iid,
                    "is_demo": "true",
                    "created_at": (datetime.combine(TODAY - timedelta(days=45), datetime.min.time())).isoformat(),
                    "author": "DEMO-ADV-USER-01",
                    "note_text": "Education fee payment scheduled; withdraw from liquid sleeve. DEMO DATA.",
                    "source": "manual",
                    "transcript_local": "false",
                }
            )
            continue
        if inv["tier"] == "high_visibility" or (hash(iid) % 5 == 0):
            rows.append(
                {
                    "note_id": f"DEMO-NOTE-{iid.split('-')[-1]}-1",
                    "investor_id": iid,
                    "is_demo": "true",
                    "created_at": (datetime.combine(TODAY - timedelta(days=random.randint(10, 200)), datetime.min.time())).isoformat(),
                    "author": "DEMO-ADV-USER-01",
                    "note_text": f"Routine check-in. Risk={inv['risk_profile']}. DEMO DATA.",
                    "source": "manual",
                    "transcript_local": "false",
                }
            )
    return rows


def build_sample_transactions() -> list[dict]:
    """Layer-1 sample: spending/income — NOT portfolio performance."""
    rows = []
    users = ["txn-user-a", "txn-user-b", "txn-user-c"]
    cats = [
        ("Salary Credit", "Income", "credit", 85000),
        ("Swiggy Order", "Food Delivery", "debit", 420),
        ("Petrol Pump", "Fuel", "debit", 2500),
        ("Amazon Apparel", "Clothing", "debit", 1899),
        ("Electricity Bill", "Utilities", "debit", 2100),
        ("SIP DEMO-NOT-LINKED", "Transfers", "debit", 10000),
    ]
    tid = 1
    for u in users:
        for day in range(1, 45):
            d = TODAY - timedelta(days=day)
            for desc, cat, typ, amt in cats:
                if typ == "credit" and day % 30 != 1:
                    continue
                if typ == "debit" and random.random() > 0.35:
                    continue
                bad_date = day == 7 and u == "txn-user-b"
                rows.append(
                    {
                        "transaction_id": f"TXN-{tid:05d}",
                        "user_id": u,
                        "date": "########" if bad_date else d.isoformat(),
                        "time": f"{random.randint(8,20):02d}:{random.randint(0,59):02d}:00",
                        "description": f"  {desc}  ",
                        "category": cat if day % 11 else "",
                        "amount": str(amt) if day != 13 else "abc",
                        "currency": "INR",
                        "type": typ.upper() if day % 5 else typ,
                        "payment_mode": random.choice(["UPI", "Card", "NetBanking", ""]),
                        "city": random.choice(["Pune", "Mumbai", "", "Bengaluru"]),
                    }
                )
                tid += 1
    return rows


def main() -> None:
    investors = build_investors()
    goals = build_goals(investors)
    holdings = build_holdings(investors, goals)
    returns = build_returns(investors, goals)
    cashflows = build_cashflows(investors)
    advice = build_advice(investors)
    notes = build_notes(investors)
    txns = build_sample_transactions()

    write_csv(
        OUT / "synthetic_investors.csv",
        list(investors[0].keys()),
        investors,
    )
    write_csv(OUT / "synthetic_goals.csv", list(goals[0].keys()), goals)
    write_csv(OUT / "synthetic_holdings.csv", list(holdings[0].keys()), holdings)
    write_csv(OUT / "synthetic_returns.csv", list(returns[0].keys()), returns)
    write_csv(OUT / "synthetic_cashflows.csv", list(cashflows[0].keys()), cashflows)
    write_csv(OUT / "synthetic_advice.csv", list(advice[0].keys()), advice)
    write_csv(OUT / "synthetic_notes.csv", list(notes[0].keys()), notes)
    write_csv(OUT / "sample_transactions.csv", list(txns[0].keys()), txns)

    print(f"\nTotal demo investors: {len(investors)}")
    print(f"  high_visibility: {sum(1 for i in investors if i['tier']=='high_visibility')}")
    print(f"  long_tail: {sum(1 for i in investors if i['tier']=='long_tail')}")


if __name__ == "__main__":
    main()
