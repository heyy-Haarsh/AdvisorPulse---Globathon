"""
Optional QuantStats cross-check on DEMO monthly return series.

Never fed from transaction CSV. Graceful fallback if quantstats is not installed.
"""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from analytics.portfolio import DataStore
from domain.evidence import ConfidenceLevel, envelope


def _native_drawdown(returns: pd.Series) -> dict[str, float]:
    wealth = (1 + returns).cumprod()
    peak = wealth.cummax()
    dd = wealth / peak - 1
    return {
        "max_drawdown": float(dd.min()) if len(dd) else float("nan"),
        "volatility_monthly": float(returns.std()) if len(returns) else float("nan"),
        "mean_monthly": float(returns.mean()) if len(returns) else float("nan"),
    }


def performance_crosscheck(store: DataStore, investor_id: str) -> dict[str, Any]:
    rets = store.returns[store.returns["investor_id"] == investor_id].sort_values("period")
    if rets.empty:
        return {
            "available": False,
            "message": "Insufficient return series",
            "evidence": envelope(
                "No returns for QuantStats/native cross-check",
                confidence=ConfidenceLevel.INSUFFICIENT,
                missing_data=["portfolio_returns"],
            ),
        }

    series = pd.Series(
        rets["portfolio_return_pct"].astype(float).values / 100.0,
        index=pd.to_datetime(rets["period_end_date"]),
    )
    bench = pd.Series(
        rets["benchmark_return_pct"].astype(float).values / 100.0,
        index=pd.to_datetime(rets["period_end_date"]),
    )

    native = _native_drawdown(series)
    # Annualize roughly from monthly
    native["vol_ann_approx"] = float(native["volatility_monthly"] * np.sqrt(12)) if native["volatility_monthly"] == native["volatility_monthly"] else None
    native["sharpe_ann_approx"] = None
    if native["volatility_monthly"] and native["volatility_monthly"] > 1e-9:
        native["sharpe_ann_approx"] = float(
            (native["mean_monthly"] * 12) / (native["volatility_monthly"] * np.sqrt(12))
        )

    qs_block: dict[str, Any] = {"used": False, "note": "quantstats not installed — native fallback only"}
    try:
        import quantstats as qs  # type: ignore

        qs_block = {
            "used": True,
            "max_drawdown": float(qs.stats.max_drawdown(series)),
            "volatility": float(qs.stats.volatility(series, periods=12)),
            "sharpe": float(qs.stats.sharpe(series, periods=12)),
            "benchmark_sharpe": float(qs.stats.sharpe(bench, periods=12)),
            "library": "quantstats",
        }
    except Exception as e:
        qs_block = {"used": False, "note": f"quantstats unavailable ({e})"}

    return {
        "available": True,
        "investor_id": investor_id,
        "periods": int(len(series)),
        "native": native,
        "quantstats": qs_block,
        "methodology": (
            "Computed from DEMO monthly portfolio_return_pct series. "
            "Not transaction cash-flow data. Monthly periods → annualization is approximate."
        ),
        "evidence": envelope(
            "Performance cross-check on DEMO returns",
            confidence=ConfidenceLevel.VERIFIED,
            evidence=[{"source": "synthetic_returns.csv", "record_ids": [investor_id]}],
            limitations=["DEMO data", "Monthly series annualization is approximate"],
        ),
        "is_demo": True,
    }
