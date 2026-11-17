import re
import threading
import time
from typing import Optional

import feedparser
import requests

from .universe import name_of

FEEDS = {
    "Economic Times Markets": "https://economictimes.indiatimes.com/markets/stocks/rssfeeds/2146842.cms",
    "Moneycontrol": "https://www.moneycontrol.com/rss/marketreports.xml",
    "Mint Markets": "https://www.livemint.com/rss/markets",
}
POS = {"surge", "gain", "gains", "rally", "rallies", "jumps", "jump", "rises", "rise", "up", "high", "record", "profit",
       "growth", "beats", "strong", "upgrade", "buy", "bullish", "soars", "outperform", "wins", "order", "positive"}
NEG = {"fall", "falls", "drops", "drop", "slump", "plunge", "plunges", "loss", "losses", "weak", "downgrade", "sell",
       "bearish", "cuts", "cut", "miss", "misses", "fraud", "probe", "penalty", "decline", "declines", "crash", "low",
       "negative", "debt", "default", "ban"}
_cache: dict = {}
_lock = threading.Lock()
UA = {"User-Agent": "Mozilla/5.0 (IntradaySathi)"}


def sentiment(text: str) -> dict:
    words = re.findall(r"[a-z]+", text.lower())
    p, n = sum(w in POS for w in words), sum(w in NEG for w in words)
    score = 0.0 if p + n == 0 else (p - n) / (p + n)
    label = "positive" if score > 0.2 else "negative" if score < -0.2 else "neutral"
    return {"score": round(score, 2), "label": label}


def _feed(name: str, url: str) -> list[dict]:
    with _lock:
        hit = _cache.get(url)
    if hit and time.time() - hit[0] < 600:
        return hit[1]
    try:
        r = requests.get(url, headers=UA, timeout=10)
        parsed = feedparser.parse(r.content)
        items = [{"title": e.get("title", ""), "link": e.get("link", ""), "source": name,
                  "published": e.get("published", ""), "summary": re.sub(r"<[^>]+>", "", e.get("summary", ""))[:300]}
                 for e in parsed.entries[:40]]
    except Exception:
        items = []
    with _lock:
        _cache[url] = (time.time(), items)
    return items


def get_news(symbol: Optional[str] = None, limit: int = 20) -> dict:
    items, failed = [], []
    for name, url in FEEDS.items():
        got = _feed(name, url)
        if not got:
            failed.append(name)
        items += got
    general = True
    if symbol:
        cname = (name_of(symbol) or "").lower()
        key = cname.split()[0] if cname else ""
        keys = [k for k in {symbol.lower(), key} if len(k) >= 3]
        matched = [i for i in items if any(k in (i["title"] + " " + i["summary"]).lower() for k in keys)]
        if matched:
            items, general = matched, False
    for i in items:
        i["sentiment"] = sentiment(i["title"] + " " + i["summary"])
    scores = [i["sentiment"]["score"] for i in items[:limit]]
    avg = round(sum(scores) / len(scores), 2) if scores else 0.0
    msg = ""
    if failed:
        msg = "Unavailable feeds: " + ", ".join(failed) + ". "
    if symbol and general and items:
        msg += f"No headlines mention {symbol}; showing general market news. "
    if not items:
        msg += "No news could be fetched right now."
    return {"items": items[:limit], "avg_sentiment": avg, "available": bool(items), "message": msg.strip(),
            "sentiment_method": "Simple keyword scoring of headlines; indicative only."}


def fundamentals(symbol: str) -> dict:
    from .data import yahoo_ticker
    import yfinance as yf
    keys = {"name": "longName", "sector": "sector", "industry": "industry", "market_cap": "marketCap",
            "pe": "trailingPE", "forward_pe": "forwardPE", "pb": "priceToBook", "dividend_yield": "dividendYield",
            "roe": "returnOnEquity", "debt_to_equity": "debtToEquity", "profit_margin": "profitMargins",
            "week52_high": "fiftyTwoWeekHigh", "week52_low": "fiftyTwoWeekLow", "beta": "beta"}
    try:
        info = yf.Ticker(yahoo_ticker(symbol)).info or {}
    except Exception:
        info = {}
    def clean(v):
        return None if isinstance(v, float) and (v != v or v in (float("inf"), float("-inf"))) else v

    data = {k: clean(info.get(v)) for k, v in keys.items()}
    ok = any(v is not None for v in data.values())
    missing = [k for k, v in data.items() if v is None]
    return {"symbol": symbol, "available": ok, "data": data, "unavailable_fields": missing,
            "message": "" if ok else "Fundamentals unavailable from Yahoo Finance right now.",
            "source": "Yahoo Finance (free, may be delayed or incomplete)"}


def announcements(symbol: str) -> dict:
    try:
        s = requests.Session()
        s.headers.update({"User-Agent": "Mozilla/5.0", "Accept-Language": "en-US,en;q=0.9"})
        s.get("https://www.nseindia.com", timeout=8)
        r = s.get("https://www.nseindia.com/api/corporate-announcements",
                  params={"index": "equities", "symbol": symbol}, timeout=8)
        r.raise_for_status()
        items = [{"subject": x.get("desc", ""), "detail": (x.get("attchmtText") or "")[:250],
                  "date": x.get("an_dt", ""), "link": x.get("attchmtFile", "")} for x in r.json()[:15]]
        return {"available": True, "items": items, "message": ""}
    except Exception:
        return {"available": False, "items": [],
                "message": "NSE announcements unavailable: NSE often blocks automated or cloud requests. Check nseindia.com directly."}
