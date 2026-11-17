import numpy as np
import pandas as pd

from . import db
from .config import INITIAL_BALANCE


def performance() -> dict:
    closed = db.rows("SELECT * FROM trades WHERE status='CLOSED' ORDER BY closed_at")
    empty = {"total_trades": 0, "win_rate": 0.0, "profit_factor": None, "max_drawdown": 0.0,
             "max_drawdown_pct": 0.0, "total_pnl": 0.0, "avg_pnl": 0.0, "ai_trade_accuracy": None,
             "ai_trades": 0, "daily": [], "weekly": [], "monthly": [],
             "note": "No completed trades yet. Metrics need many trades to be meaningful."}
    if not closed:
        return empty
    pnl = np.array([c["pnl"] or 0.0 for c in closed])
    gp, gl = pnl[pnl > 0].sum(), -pnl[pnl < 0].sum()
    equity = INITIAL_BALANCE + np.cumsum(pnl)
    peak = np.maximum.accumulate(np.concatenate([[INITIAL_BALANCE], equity]))[1:]
    dd = peak - equity
    ai = [c for c in closed if c["source"] == "auto"]
    df = pd.DataFrame({"t": pd.to_datetime([c["closed_at"] for c in closed], utc=True).tz_convert("Asia/Kolkata"), "pnl": pnl})

    def group(fmt: str, n: int) -> list[dict]:
        g = df.groupby(df["t"].dt.strftime(fmt))["pnl"].agg(["sum", "count"])
        return [{"period": k, "pnl": round(float(v["sum"]), 2), "trades": int(v["count"])} for k, v in g.tail(n).iterrows()]

    return {"total_trades": len(closed), "win_rate": round(float((pnl > 0).mean() * 100), 2),
            "profit_factor": round(float(gp / gl), 2) if gl > 0 else None,
            "max_drawdown": round(float(dd.max()), 2), "max_drawdown_pct": round(float((dd / peak).max() * 100), 2),
            "total_pnl": round(float(pnl.sum()), 2), "avg_pnl": round(float(pnl.mean()), 2),
            "ai_trades": len(ai),
            "ai_trade_accuracy": round(sum(1 for c in ai if (c["pnl"] or 0) > 0) / len(ai) * 100, 2) if ai else None,
            "daily": group("%Y-%m-%d", 30), "weekly": group("%G-W%V", 12), "monthly": group("%Y-%m", 12),
            "note": "Simulated results; no brokerage/slippage/taxes. Small samples are statistically unreliable."}
