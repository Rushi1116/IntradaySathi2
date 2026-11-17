import threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from . import analytics, db, ml, news, paper, universe
from .auto import trader
from .config import DISCLAIMER, LOAD_FULL_UNIVERSE, market_open, now_ist
from .data import get_candles, quote
from .indicators import add_indicators


@asynccontextmanager
async def lifespan(_: FastAPI):
    db.init_db()
    if LOAD_FULL_UNIVERSE:
        threading.Thread(target=universe.load_full_universe, daemon=True).start()
    trader.ensure_thread()
    yield


app = FastAPI(title="Intraday Sathi API", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


def sym(s: str) -> str:
    return s.upper().strip().removesuffix(".NS")


def check_interval(i: str) -> str:
    if i not in ("5m", "15m"):
        raise HTTPException(400, "interval must be 5m or 15m")
    return i


def bad(e: Exception, code: int = 400):
    raise HTTPException(code, str(e))


class OrderIn(BaseModel):
    symbol: str
    side: str
    qty: int = Field(gt=0)
    stop_loss: Optional[float] = None
    target: Optional[float] = None
    interval: str = "5m"


class AutoCfgIn(BaseModel):
    daily_loss_limit: Optional[float] = None
    max_trades: Optional[int] = None
    max_open: Optional[int] = None
    min_confidence: Optional[float] = None
    interval: Optional[str] = None
    watchlist: Optional[list[str]] = None


@app.get("/")
def root():
    return {"app": "Intraday Sathi API", "status": "ok", "health": "/health", "docs": "/docs"}


@app.get("/health")
def health():
    return {"status": "ok", "time_ist": now_ist().isoformat(), "market_open": market_open()}


@app.get("/disclaimer")
def disclaimer():
    return {"text": DISCLAIMER}


@app.get("/stocks/search")
def stocks_search(q: str = ""):
    return {"items": universe.search(q)}


@app.get("/market/overview")
def market_overview():
    idx = {"NIFTY 50": "^NSEI", "BANK NIFTY": "^NSEBANK", "SENSEX": "^BSESN"}
    items = []
    for name, s in idx.items():
        q = quote(s)
        items.append({"name": name, **(q or {"price": None, "change": None, "change_pct": None, "unavailable": True})})
    return {"items": items, "market_open": market_open(), "note": "Index data delayed; may be unavailable."}


@app.get("/candles/{symbol}")
def candles(symbol: str, interval: str = "5m", limit: int = 120):
    df = get_candles(sym(symbol), check_interval(interval))
    if df is None:
        raise HTTPException(503, f"No candle data for {symbol} (delayed free source unavailable or symbol invalid)")
    d = add_indicators(df).tail(max(10, min(limit, 400)))
    out = [{"t": i.isoformat(), "o": r.open, "h": r.high, "l": r.low, "c": r.close, "v": r.volume,
            "ema9": r.ema9, "ema21": r.ema21, "vwap": r.vwap, "rsi": r.rsi, "macd": r.macd,
            "macd_signal": r.macd_signal, "atr": r.atr, "vol_ratio": r.vol_ratio} for i, r in d.iterrows()]
    return {"symbol": sym(symbol), "interval": interval, "items": out}


@app.get("/signals/{symbol}")
def signal(symbol: str, interval: str = "5m"):
    try:
        return ml.predict(sym(symbol), check_interval(interval))
    except LookupError as e:
        bad(e, 503)


@app.get("/signals")
def signals(interval: str = "5m"):
    check_interval(interval)
    wl = trader.cfg["watchlist"]

    def one(s: str):
        try:
            r = ml.predict(s, interval)
            return {k: r[k] for k in ("symbol", "signal", "confidence", "price", "model_type", "levels", "risk_reward")}
        except Exception:
            return None

    with ThreadPoolExecutor(max_workers=5) as ex:
        items = [r for r in ex.map(one, wl) if r]
    items.sort(key=lambda r: (r["signal"] == "HOLD", -r["confidence"]))
    return {"items": items, "interval": interval, "note": "Delayed data. Not advice."}


@app.post("/paper/orders")
def order(o: OrderIn):
    try:
        return paper.place_order(sym(o.symbol), o.side, o.qty, o.stop_loss, o.target, check_interval(o.interval), "manual")
    except ValueError as e:
        bad(e)


@app.post("/paper/positions/{trade_id}/close")
def close_position(trade_id: int):
    try:
        return paper.close_trade(trade_id, reason="manual")
    except ValueError as e:
        bad(e)


@app.get("/paper/portfolio")
def portfolio():
    return paper.portfolio()


@app.get("/paper/trades")
def trades(limit: int = 50):
    return {"items": db.rows("SELECT id, symbol, side, qty, entry, exit_price, pnl, exit_reason, source, status, opened_at, closed_at "
                             "FROM trades ORDER BY id DESC LIMIT ?", (max(1, min(limit, 200)),))}


@app.post("/paper/reset")
def reset():
    trader.stop()
    paper.reset()
    return {"ok": True, "message": "Virtual account reset."}


@app.get("/auto/status")
def auto_status():
    return trader.snapshot()


@app.post("/auto/config")
def auto_config(c: AutoCfgIn):
    try:
        return trader.set_cfg(c.model_dump(exclude_none=True))
    except ValueError as e:
        bad(e)


@app.post("/auto/{action}")
def auto_action(action: str):
    try:
        if action == "start": trader.start()
        elif action == "pause": trader.pause()
        elif action == "resume": trader.resume()
        elif action == "stop": trader.stop()
        elif action == "emergency": trader.emergency_stop()
        else: raise HTTPException(404, "unknown action")
    except ValueError as e:
        bad(e)
    return trader.snapshot()


@app.get("/ai/performance")
def ai_performance():
    return analytics.performance()


@app.get("/ai/models")
def ai_models():
    return {"items": ml.list_models(),
            "limitations": "Models are trained on ~60 days of delayed free data for a few large stocks. "
                           "Validation accuracy is on recent held-out data only and can overstate live performance."}


@app.post("/ai/train")
def ai_train(interval: str = "5m"):
    try:
        return ml.train(check_interval(interval))
    except ValueError as e:
        bad(e)


@app.post("/ai/retrain")
def ai_retrain(interval: str = "5m", force: bool = False):
    try:
        return ml.retrain_if_ready(check_interval(interval), force)
    except ValueError as e:
        bad(e)


@app.post("/ai/rollback")
def ai_rollback(interval: str = "5m", model_id: Optional[int] = None):
    try:
        return ml.rollback(check_interval(interval), model_id)
    except ValueError as e:
        bad(e)


@app.get("/news")
def get_news(symbol: Optional[str] = Query(None)):
    return news.get_news(sym(symbol) if symbol else None)


@app.get("/fundamentals/{symbol}")
def fundamentals(symbol: str):
    return news.fundamentals(sym(symbol))


@app.get("/announcements/{symbol}")
def announcements(symbol: str):
    return news.announcements(sym(symbol))
