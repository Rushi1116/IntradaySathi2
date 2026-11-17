import json
import os
from datetime import datetime
from typing import Optional

import numpy as np
import pandas as pd
import xgboost as xgb

from . import db
from .config import MODEL_DIR, RETRAIN_MIN_TRADES, TRAIN_SYMBOLS, now_ist
from .data import get_candles
from .indicators import add_indicators
from .universe import CORE

FEATURE_COLS = ["ema_diff", "close_ema9", "rsi", "macd_hist_n", "macd_n", "vwap_dist",
                "atr_pct", "vol_ratio", "ret1", "ret3", "ret6"]
HORIZON = {"5m": 6, "15m": 4}  # bars ahead used for the label
LABELS = ["SELL", "HOLD", "BUY"]
MIN_SAMPLES = 300
RR = 1.5
_models: dict = {}


def make_features(d: pd.DataFrame) -> pd.DataFrame:
    f = pd.DataFrame(index=d.index)
    f["ema_diff"] = (d["ema9"] - d["ema21"]) / d["close"]
    f["close_ema9"] = (d["close"] - d["ema9"]) / d["close"]
    f["rsi"] = d["rsi"]
    f["macd_hist_n"] = d["macd_hist"] / d["close"]
    f["macd_n"] = d["macd"] / d["close"]
    f["vwap_dist"] = (d["close"] - d["vwap"]) / d["close"]
    f["atr_pct"] = d["atr"] / d["close"]
    f["vol_ratio"] = d["vol_ratio"]
    f["ret1"] = d["close"].pct_change(1)
    f["ret3"] = d["close"].pct_change(3)
    f["ret6"] = d["close"].pct_change(6)
    return f.replace([np.inf, -np.inf], np.nan)


def make_labels(d: pd.DataFrame, interval: str) -> pd.Series:
    h = HORIZON[interval]
    fut = d["close"].shift(-h) / d["close"] - 1
    thr = 0.8 * d["atr"] / d["close"]
    lab = pd.Series(1.0, index=d.index)
    lab[fut > thr] = 2.0
    lab[fut < -thr] = 0.0
    day = pd.Series(np.asarray(d.index.date), index=d.index)
    same_day = day == day.shift(-h)
    lab[~same_day] = np.nan
    lab[fut.isna()] = np.nan
    return lab


def build_dataset(interval: str, symbols: list[str]):
    xtr, ytr, xva, yva = [], [], [], []
    for s in symbols:
        df = get_candles(s, interval, period="60d")
        if df is None or len(df) < 120:
            continue
        d = add_indicators(df)
        f, lab = make_features(d), make_labels(d, interval)
        m = f.notna().all(axis=1) & lab.notna()
        f, lab = f[m], lab[m]
        cut = int(len(f) * 0.8)
        xtr.append(f.iloc[:cut]); ytr.append(lab.iloc[:cut])
        xva.append(f.iloc[cut:]); yva.append(lab.iloc[cut:])
    if not xtr:
        raise ValueError("No candle data could be downloaded (Yahoo Finance may be unavailable).")
    return pd.concat(xtr), pd.concat(ytr), pd.concat(xva), pd.concat(yva)


def active_model(interval: str) -> Optional[dict]:
    r = db.rows("SELECT * FROM model_versions WHERE interval=? AND active=1 ORDER BY id DESC LIMIT 1", (interval,))
    return r[0] if r else None


def _next_version(interval: str) -> str:
    n = db.rows("SELECT COUNT(*) AS n FROM model_versions WHERE interval=?", (interval,))[0]["n"]
    return f"{interval}-v{n + 1}"


def train(interval: str, extra: Optional[list[tuple[dict, int]]] = None, note: str = "") -> dict:
    if interval not in HORIZON:
        raise ValueError("interval must be 5m or 15m")
    os.makedirs(MODEL_DIR, exist_ok=True)
    symbols = list(CORE.keys())[:TRAIN_SYMBOLS]
    xtr, ytr, xva, yva = build_dataset(interval, symbols)
    w = np.ones(len(xtr))
    if extra:
        ex = pd.DataFrame([e[0] for e in extra])[FEATURE_COLS]
        xtr = pd.concat([xtr, ex])
        ytr = pd.concat([ytr, pd.Series([float(e[1]) for e in extra])])
        w = np.concatenate([w, np.full(len(ex), 3.0)])
    if len(xtr) < MIN_SAMPLES or len(xva) < 50:
        raise ValueError(f"Not enough data to train ({len(xtr)} train / {len(xva)} validation rows).")
    params = {"objective": "multi:softprob", "num_class": 3, "max_depth": 4, "eta": 0.08,
              "subsample": 0.8, "colsample_bytree": 0.8, "eval_metric": "mlogloss", "seed": 42}
    booster = xgb.train(params, xgb.DMatrix(xtr[FEATURE_COLS], label=ytr.values, weight=w), num_boost_round=150)
    proba = booster.predict(xgb.DMatrix(xva[FEATURE_COLS]))
    acc = float((proba.argmax(axis=1) == yva.values).mean())
    baseline = float(yva.value_counts(normalize=True).max())
    version = _next_version(interval)
    path = os.path.join(MODEL_DIR, f"{version}.json")
    booster.save_model(path)
    prev = active_model(interval)
    accepted = prev is None or acc >= float(prev["accuracy"]) - 0.02
    notes = (f"val_acc={acc:.3f} majority_baseline={baseline:.3f} train_rows={len(xtr)} "
             f"val_rows={len(xva)} {note}").strip()
    if not accepted:
        notes += f" REJECTED: worse than active {prev['version']} ({prev['accuracy']:.3f})"
    mid = db.execute(
        "INSERT INTO model_versions(interval, version, path, accuracy, samples, created_at, active, notes) "
        "VALUES(?,?,?,?,?,?,?,?)",
        (interval, version, path, acc, len(xtr), now_ist().isoformat(), 0, notes))
    if accepted:
        activate(mid)
    return {"version": version, "accuracy": round(acc, 4), "baseline_accuracy": round(baseline, 4),
            "activated": accepted, "notes": notes}


def activate(model_id: int) -> dict:
    r = db.rows("SELECT * FROM model_versions WHERE id=?", (model_id,))
    if not r:
        raise ValueError("Model version not found")
    db.execute("UPDATE model_versions SET active=0 WHERE interval=?", (r[0]["interval"],))
    db.execute("UPDATE model_versions SET active=1 WHERE id=?", (model_id,))
    return r[0]


def rollback(interval: str, model_id: Optional[int] = None) -> dict:
    cur = active_model(interval)
    if model_id is None:
        if not cur:
            raise ValueError("No active model to roll back from")
        older = db.rows("SELECT * FROM model_versions WHERE interval=? AND id<? ORDER BY id DESC LIMIT 1",
                        (interval, cur["id"]))
        if not older:
            raise ValueError("No earlier model version available")
        model_id = older[0]["id"]
    return activate(model_id)


def list_models() -> list[dict]:
    return db.rows("SELECT id, interval, version, accuracy, samples, created_at, active, notes "
                   "FROM model_versions ORDER BY id DESC")


def _load(path: str):
    if path not in _models:
        b = xgb.Booster()
        b.load_model(path)
        _models[path] = b
    return _models[path]


def levels(price: float, atr: float):
    risk = max(atr, price * 0.001)
    return ({"buy": {"stop_loss": round(price - risk, 2), "target": round(price + RR * risk, 2)},
             "sell": {"stop_loss": round(price + risk, 2), "target": round(price - RR * risk, 2)}}, risk)


def predict(symbol: str, interval: str = "5m") -> dict:
    df = get_candles(symbol, interval)
    if df is None or len(df) < 40:
        raise LookupError(f"Candle data unavailable for {symbol}")
    d = add_indicators(df)
    f = make_features(d).iloc[[-1]]
    if f.isna().any(axis=None):
        f = f.fillna(0.0)
    last = d.iloc[-1]
    price, atr = float(last["close"]), float(last["atr"])
    lv, risk = levels(price, atr)
    feats = {k: float(f[k].iloc[0]) for k in FEATURE_COLS}
    meta = active_model(interval)
    if meta and os.path.exists(meta["path"]):
        p = _load(meta["path"]).predict(xgb.DMatrix(f[FEATURE_COLS]))[0]
        idx = int(np.argmax(p))
        signal, conf = LABELS[idx], float(p[idx])
        probs = {"sell": float(p[0]), "hold": float(p[1]), "buy": float(p[2])}
        mtype, mver = "xgboost", meta["version"]
    else:
        bull = last["ema9"] > last["ema21"] and last["macd_hist"] > 0 and last["close"] > last["vwap"]
        bear = last["ema9"] < last["ema21"] and last["macd_hist"] < 0 and last["close"] < last["vwap"]
        signal = "BUY" if bull else "SELL" if bear else "HOLD"
        conf, probs = 0.5, {"sell": 0.0, "hold": 0.0, "buy": 0.0}
        mtype, mver = "rule_based_fallback", "none"
    return {
        "symbol": symbol, "interval": interval, "signal": signal, "confidence": round(conf, 4),
        "probabilities": {k: round(v, 4) for k, v in probs.items()},
        "price": round(price, 2), "atr": round(atr, 3), "levels": lv, "risk_per_share": round(risk, 3),
        "risk_reward": RR, "model_type": mtype, "model_version": mver, "features": feats,
        "as_of": d.index[-1].isoformat(),
        "note": "Delayed data. Model confidence is a statistical score, not a probability of profit.",
    }


def retrain_if_ready(interval: str, force: bool = False) -> dict:
    meta = active_model(interval)
    since = meta["created_at"] if meta else "1970-01-01"
    trades = db.rows("SELECT * FROM trades WHERE status='CLOSED' AND interval=? AND features IS NOT NULL "
                     "AND closed_at>? AND source='auto'", (interval, since))
    if len(trades) < RETRAIN_MIN_TRADES and not force:
        return {"retrained": False, "interval": interval,
                "reason": f"Only {len(trades)} new completed AI trades; need {RETRAIN_MIN_TRADES}."}
    extra = []
    for t in trades:
        win = (t["pnl"] or 0) > 0
        label = (2 if win else 1) if t["side"] == "BUY" else (0 if win else 1)
        extra.append((json.loads(t["features"]), label))
    res = train(interval, extra, note=f"outcome_rows={len(extra)}")
    res["retrained"] = True
    return res
