import json
from typing import Optional

from . import db
from .config import INITIAL_BALANCE, ENFORCE_MARKET_HOURS, now_ist
from .data import get_candles


def latest_price(symbol: str) -> Optional[float]:
    df = get_candles(symbol, "5m")
    return None if df is None or df.empty else float(df["close"].iloc[-1])


def open_trades() -> list[dict]:
    return db.rows("SELECT * FROM trades WHERE status='OPEN' ORDER BY id DESC")


def place_order(symbol: str, side: str, qty: int, stop_loss: Optional[float] = None,
                target: Optional[float] = None, interval: str = "5m", source: str = "manual",
                features: Optional[dict] = None, model_version: Optional[str] = None,
                price: Optional[float] = None) -> dict:
    side = side.upper()
    if side not in ("BUY", "SELL"):
        raise ValueError("side must be BUY or SELL")
    if qty <= 0:
        raise ValueError("quantity must be positive")
    price = price if price is not None else latest_price(symbol)
    if price is None:
        raise ValueError(f"No price available for {symbol}")
    if stop_loss is not None and ((side == "BUY" and stop_loss >= price) or (side == "SELL" and stop_loss <= price)):
        raise ValueError("stop-loss is on the wrong side of the entry price")
    if target is not None and ((side == "BUY" and target <= price) or (side == "SELL" and target >= price)):
        raise ValueError("target is on the wrong side of the entry price")
    cost = qty * price
    cash = db.get_cash()
    if cost > cash:
        raise ValueError(f"Insufficient virtual balance: need {cost:,.2f}, have {cash:,.2f}")
    db.set_cash(cash - cost)  # SELL (short) blocks the same notional as margin
    tid = db.execute(
        "INSERT INTO trades(symbol, side, qty, entry, stop_loss, target, interval, source, status, opened_at, features, model_version) "
        "VALUES(?,?,?,?,?,?,?,?,'OPEN',?,?,?)",
        (symbol, side, qty, round(price, 2), stop_loss, target, interval, source, now_ist().isoformat(),
         json.dumps(features) if features else None, model_version))
    return db.rows("SELECT * FROM trades WHERE id=?", (tid,))[0]


def close_trade(trade_id: int, price: Optional[float] = None, reason: str = "manual") -> dict:
    r = db.rows("SELECT * FROM trades WHERE id=? AND status='OPEN'", (trade_id,))
    if not r:
        raise ValueError("Open position not found")
    t = r[0]
    price = price if price is not None else latest_price(t["symbol"])
    if price is None:
        raise ValueError(f"No price available for {t['symbol']}")
    pnl = (price - t["entry"]) * t["qty"] if t["side"] == "BUY" else (t["entry"] - price) * t["qty"]
    pnl = round(pnl, 2)
    db.set_cash(db.get_cash() + t["entry"] * t["qty"] + pnl)
    db.execute("UPDATE trades SET status='CLOSED', closed_at=?, exit_price=?, pnl=?, exit_reason=? WHERE id=?",
               (now_ist().isoformat(), round(price, 2), pnl, reason, trade_id))
    return db.rows("SELECT * FROM trades WHERE id=?", (trade_id,))[0]


def close_all(reason: str) -> int:
    n = 0
    for t in open_trades():
        try:
            close_trade(t["id"], reason=reason)
            n += 1
        except ValueError:
            pass
    return n


def monitor() -> list[dict]:
    """Check stop-loss/target/square-off for all open positions."""
    closed = []
    n = now_ist()
    squareoff = ENFORCE_MARKET_HOURS and (n.hour, n.minute) >= (15, 15)
    for t in open_trades():
        price = latest_price(t["symbol"])
        if price is None:
            continue
        reason = None
        if t["side"] == "BUY":
            if t["stop_loss"] and price <= t["stop_loss"]: reason = "stop_loss"
            elif t["target"] and price >= t["target"]: reason = "target"
        else:
            if t["stop_loss"] and price >= t["stop_loss"]: reason = "stop_loss"
            elif t["target"] and price <= t["target"]: reason = "target"
        if reason is None and squareoff:
            reason = "intraday_squareoff"
        if reason:
            closed.append(close_trade(t["id"], price, reason))
    return closed


def portfolio() -> dict:
    cash = db.get_cash()
    positions, invested, unreal = [], 0.0, 0.0
    for t in open_trades():
        ltp = latest_price(t["symbol"]) or t["entry"]
        u = (ltp - t["entry"]) * t["qty"] if t["side"] == "BUY" else (t["entry"] - ltp) * t["qty"]
        invested += t["entry"] * t["qty"]
        unreal += u
        positions.append({**{k: t[k] for k in ("id", "symbol", "side", "qty", "entry", "stop_loss", "target", "source", "opened_at")},
                          "ltp": round(ltp, 2), "unrealized_pnl": round(u, 2)})
    today = now_ist().strftime("%Y-%m-%d")
    closed = db.rows("SELECT pnl, closed_at FROM trades WHERE status='CLOSED'")
    realized = sum(c["pnl"] or 0 for c in closed)
    realized_today = sum(c["pnl"] or 0 for c in closed if (c["closed_at"] or "").startswith(today))
    equity = cash + invested + unreal
    return {"initial_balance": INITIAL_BALANCE, "cash": round(cash, 2), "invested": round(invested, 2),
            "unrealized_pnl": round(unreal, 2), "realized_pnl": round(realized, 2),
            "today_pnl": round(realized_today + unreal, 2), "today_realized": round(realized_today, 2),
            "equity": round(equity, 2), "total_return_pct": round((equity - INITIAL_BALANCE) / INITIAL_BALANCE * 100, 2),
            "positions": positions}


def trades_today(source: Optional[str] = None) -> int:
    today = now_ist().strftime("%Y-%m-%d")
    q = "SELECT COUNT(*) AS n FROM trades WHERE opened_at LIKE ?"
    a: tuple = (today + "%",)
    if source:
        q += " AND source=?"
        a += (source,)
    return db.rows(q, a)[0]["n"]


def reset() -> None:
    db.execute("DELETE FROM trades")
    db.set_cash(INITIAL_BALANCE)
