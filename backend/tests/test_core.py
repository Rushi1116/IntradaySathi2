import numpy as np
import pandas as pd
import pytest

from app import analytics, db, indicators, ml, paper
from app.auto import trader


def synthetic(seed: int, n: int = 700) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2025-01-01 09:15", periods=n, freq="5min", tz="Asia/Kolkata")
    close = 100 + np.cumsum(rng.normal(0, 0.3, n))
    return pd.DataFrame({"open": close, "high": close + 0.3, "low": close - 0.3, "close": close,
                         "volume": rng.integers(1000, 5000, n).astype(float)}, index=idx)


@pytest.fixture(autouse=True)
def setup(monkeypatch):
    db.init_db()
    paper.reset()
    monkeypatch.setattr(ml, "get_candles", lambda s, i="5m", period=None: synthetic(abs(hash(s)) % 1000))
    yield


def test_indicators():
    d = indicators.add_indicators(synthetic(1))
    for c in ("ema9", "ema21", "rsi", "macd", "vwap", "atr", "vol_ratio"):
        assert c in d.columns and not d[c].isna().all()
    assert d["rsi"].between(0, 100).all()


def test_labels_three_classes():
    d = indicators.add_indicators(synthetic(2))
    lab = ml.make_labels(d, "5m").dropna()
    assert set(lab.unique()) <= {0.0, 1.0, 2.0} and len(lab) > 100


def test_train_predict_rollback():
    r1 = ml.train("5m")
    assert r1["activated"] and ml.active_model("5m")["version"] == "5m-v1"
    ml.train("5m")
    s = ml.predict("RELIANCE", "5m")
    assert s["signal"] in ("BUY", "SELL", "HOLD") and 0 <= s["confidence"] <= 1
    assert s["risk_reward"] == 1.5
    active = ml.active_model("5m")
    if active["version"] != "5m-v1":
        ml.rollback("5m")
        assert ml.active_model("5m")["version"] == "5m-v1"


def test_fallback_without_model():
    assert ml.predict("TCS", "15m")["model_type"] == "rule_based_fallback"


def test_paper_trade_target_and_stop(monkeypatch):
    monkeypatch.setattr(paper, "latest_price", lambda s: 100.0)
    t = paper.place_order("TCS", "BUY", 10, 99.0, 102.0)
    assert paper.portfolio()["cash"] == 99000.0
    monkeypatch.setattr(paper, "latest_price", lambda s: 102.5)
    closed = paper.monitor()
    assert closed[0]["exit_reason"] == "target" and closed[0]["pnl"] == 25.0
    assert paper.portfolio()["cash"] == 100025.0
    monkeypatch.setattr(paper, "latest_price", lambda s: 100.0)
    paper.place_order("INFY", "SELL", 10, 101.0, 98.0)
    monkeypatch.setattr(paper, "latest_price", lambda s: 101.5)
    assert paper.monitor()[0]["exit_reason"] == "stop_loss"
    p = analytics.performance()
    assert p["total_trades"] == 2 and p["win_rate"] == 50.0


def test_validation_errors(monkeypatch):
    monkeypatch.setattr(paper, "latest_price", lambda s: 100.0)
    with pytest.raises(ValueError):
        paper.place_order("TCS", "BUY", 10, 101.0, 102.0)
    with pytest.raises(ValueError):
        paper.place_order("TCS", "BUY", 100000, 99.0, 102.0)


def test_emergency_stop(monkeypatch):
    monkeypatch.setattr(paper, "latest_price", lambda s: 100.0)
    paper.place_order("TCS", "BUY", 5)
    assert trader.emergency_stop() == 1
    assert trader.status == "emergency"
    with pytest.raises(ValueError):
        trader.start()
    trader.stop()
    trader.start()
    trader.pause()
    trader.resume()
    trader.stop()
