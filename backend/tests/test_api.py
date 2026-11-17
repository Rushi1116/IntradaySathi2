from fastapi.testclient import TestClient

from app.main import app


def test_basic_routes():
    with TestClient(app) as c:
        assert c.get("/").json()["status"] == "ok"
        assert c.get("/health").json()["status"] == "ok"
        assert "PAPER" in c.get("/disclaimer").json()["text"]
        assert any(i["symbol"] == "RELIANCE" for i in c.get("/stocks/search?q=reli").json()["items"])
        assert c.get("/paper/portfolio").json()["cash"] > 0
        assert c.get("/auto/status").json()["status"] in ("stopped", "running", "paused", "emergency")
        assert c.get("/signals/TCS?interval=1h").status_code == 400
        assert c.post("/auto/config", json={"min_confidence": 5}).status_code == 400
        assert c.get("/ai/models").status_code == 200


def test_candles_serialize(monkeypatch):
    import numpy as np
    import pandas as pd
    from app import main

    idx = pd.date_range("2025-01-01 09:15", periods=100, freq="5min", tz="Asia/Kolkata")
    c = 100 + np.cumsum(np.random.default_rng(1).normal(0, 0.3, 100))
    df = pd.DataFrame({"open": c, "high": c + 0.2, "low": c - 0.2, "close": c, "volume": np.full(100, 1000.0)}, index=idx)
    monkeypatch.setattr(main, "get_candles", lambda s, i="5m", period=None: df)
    with TestClient(main.app) as cl:
        r = cl.get("/candles/TCS?interval=5m&limit=50")
        assert r.status_code == 200 and len(r.json()["items"]) == 50
