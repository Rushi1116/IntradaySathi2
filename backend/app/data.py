import threading
import time
from typing import Optional

import pandas as pd
import yfinance as yf

from .config import CANDLE_TTL_SECONDS

_cache: dict = {}
_lock = threading.Lock()


def yahoo_ticker(symbol: str) -> str:
    s = symbol.upper().strip()
    if s.startswith("^") or s.endswith(".NS"):
        return s
    return f"{s}.NS"


def get_candles(symbol: str, interval: str = "5m", period: Optional[str] = None) -> Optional[pd.DataFrame]:
    """Return OHLCV DataFrame (IST index) or None when data is unavailable. Delayed ~15 min."""
    if interval not in ("5m", "15m"):
        raise ValueError("interval must be 5m or 15m")
    period = period or ("5d" if interval == "5m" else "10d")
    key = (symbol, interval, period)
    now = time.time()
    with _lock:
        hit = _cache.get(key)
    if hit and now - hit[0] < CANDLE_TTL_SECONDS:
        return hit[1]
    try:
        df = yf.Ticker(yahoo_ticker(symbol)).history(period=period, interval=interval, auto_adjust=False)
    except Exception:
        return hit[1] if hit else None
    if df is None or df.empty:
        return hit[1] if hit else None
    df = df.rename(columns=str.lower)[["open", "high", "low", "close", "volume"]].dropna()
    if df.empty:
        return None
    df.index = df.index.tz_localize("Asia/Kolkata") if df.index.tz is None else df.index.tz_convert("Asia/Kolkata")
    with _lock:
        _cache[key] = (now, df)
    return df


def quote(symbol: str) -> Optional[dict]:
    key = ("quote", symbol)
    now = time.time()
    with _lock:
        hit = _cache.get(key)
    if hit and now - hit[0] < 60:
        return hit[1]
    try:
        h = yf.Ticker(yahoo_ticker(symbol)).history(period="5d", interval="1d")
        if h is None or len(h) < 2:
            return None
        last, prev = float(h["Close"].iloc[-1]), float(h["Close"].iloc[-2])
        q = {"price": round(last, 2), "change": round(last - prev, 2), "change_pct": round((last - prev) / prev * 100, 2)}
        with _lock:
            _cache[key] = (now, q)
        return q
    except Exception:
        return None
