"""Generate deterministic DEMO security_positions.csv (look-through view; sleeve CSV unchanged)."""
from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"


def pick(iids: list[str], seed: str, n: int) -> list[str]:
    out: list[str] = []
    for iid in iids:
        hsh = int(hashlib.md5(f"{seed}:{iid}".encode()).hexdigest()[:8], 16)
        if hsh % 7 == 0:
            out.append(iid)
        if len(out) >= n:
            break
    return out


def main() -> None:
    h = pd.read_csv(DATA / "synthetic_holdings.csv")
    large = h[h["asset_class"] == "Equity - Large Cap"].copy()
    holders = large.drop_duplicates("investor_id").sort_values("investor_id")
    iids = holders["investor_id"].astype(str).tolist()
    rows: list[dict] = []

    rel = h[h["instrument_id"] == "DEMO-STOCK-RELIANCE_PROXY"]
    for _, r in rel.iterrows():
        qty = float(r["quantity"])
        mv = float(r["market_value"])
        px = (mv / qty) if qty else 2950.0
        rows.append(
            {
                "position_id": f"SEC-{r['investor_id']}-RELIANCE",
                "investor_id": r["investor_id"],
                "account_id": f"{r['investor_id']}-EQ",
                "holding_instrument_id": "DEMO-STOCK-RELIANCE_PROXY",
                "instrument_id": "NSE:RELIANCE",
                "symbol": "RELIANCE",
                "exchange": "NSE",
                "instrument_type": "stock",
                "exposure_kind": "direct",
                "quantity": round(qty, 4),
                "reference_price": round(px, 4),
                "market_value": round(mv, 2),
                "currency": r["currency"],
                "as_of_date": r["as_of_date"],
                "is_demo": True,
                "source_holding_id": r["holding_id"],
                "note": "Mapped from DEMO-STOCK-RELIANCE_PROXY sleeve line",
            }
        )

    specs = [
        ("DEMO-STOCK-TCS", "NSE:TCS", "TCS", "NSE", 4125.0, "INR", 0.12, 40),
        ("DEMO-STOCK-INFY", "NSE:INFY", "INFY", "NSE", 1880.0, "INR", 0.10, 35),
        ("DEMO-STOCK-HDFCBANK", "NSE:HDFCBANK", "HDFCBANK", "NSE", 1685.0, "INR", 0.11, 35),
        ("DEMO-STOCK-AAPL", "NASDAQ:AAPL", "AAPL", "NASDAQ", 228.5, "USD", 0.08, 12),
        ("DEMO-STOCK-MSFT", "NASDAQ:MSFT", "MSFT", "NASDAQ", 428.0, "USD", 0.07, 12),
    ]
    for hold_id, inst_id, sym, exch, px, ccy, frac, n in specs:
        for iid in pick(iids, hold_id, n):
            sleeve = large[large["investor_id"] == iid].iloc[0]
            sleeve_mv = float(sleeve["market_value"])
            if ccy == "USD":
                fx = 83.0
                mv = round((sleeve_mv * frac) / fx, 2)
                qty = round(mv / px, 4)
                note = (
                    f"Illustrative USD overlay ({frac:.0%} of large-cap sleeve / FX {fx}); "
                    "DEMO only — not live FX"
                )
            else:
                mv = round(sleeve_mv * frac, 2)
                qty = round(mv / px, 4)
                note = (
                    f"Deterministic carve-out view ({frac:.0%} of large-cap sleeve); "
                    "DEMO look-through — sleeve CSV unchanged"
                )
            rows.append(
                {
                    "position_id": f"SEC-{iid}-{sym}",
                    "investor_id": iid,
                    "account_id": f"{iid}-EQ",
                    "holding_instrument_id": hold_id,
                    "instrument_id": inst_id,
                    "symbol": sym,
                    "exchange": exch,
                    "instrument_type": "stock",
                    "exposure_kind": "direct",
                    "quantity": qty,
                    "reference_price": px,
                    "market_value": mv,
                    "currency": ccy,
                    "as_of_date": "2026-10-14",
                    "is_demo": True,
                    "source_holding_id": sleeve["holding_id"],
                    "note": note,
                }
            )

    df = pd.DataFrame(rows)
    out = DATA / "demo" / "security_positions.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)
    print(f"Wrote {len(df)} positions -> {out}")
    print(df.groupby("instrument_id").size().to_string())


if __name__ == "__main__":
    main()
