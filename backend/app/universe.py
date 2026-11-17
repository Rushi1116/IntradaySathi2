import csv
import io
import threading
from typing import Optional

import requests

CORE: dict[str, str] = {
    "RELIANCE": "Reliance Industries", "TCS": "Tata Consultancy Services", "HDFCBANK": "HDFC Bank",
    "ICICIBANK": "ICICI Bank", "INFY": "Infosys", "HINDUNILVR": "Hindustan Unilever", "ITC": "ITC",
    "SBIN": "State Bank of India", "BHARTIARTL": "Bharti Airtel", "KOTAKBANK": "Kotak Mahindra Bank",
    "LT": "Larsen & Toubro", "AXISBANK": "Axis Bank", "BAJFINANCE": "Bajaj Finance",
    "ASIANPAINT": "Asian Paints", "MARUTI": "Maruti Suzuki", "SUNPHARMA": "Sun Pharma",
    "TITAN": "Titan Company", "ULTRACEMCO": "UltraTech Cement", "NESTLEIND": "Nestle India",
    "WIPRO": "Wipro", "HCLTECH": "HCL Technologies", "POWERGRID": "Power Grid", "NTPC": "NTPC",
    "ONGC": "Oil and Natural Gas Corp", "TATASTEEL": "Tata Steel", "JSWSTEEL": "JSW Steel",
    "ADANIENT": "Adani Enterprises", "ADANIPORTS": "Adani Ports", "COALINDIA": "Coal India",
    "BAJAJFINSV": "Bajaj Finserv", "TECHM": "Tech Mahindra", "INDUSINDBK": "IndusInd Bank",
    "HINDALCO": "Hindalco", "DRREDDY": "Dr Reddys Laboratories", "CIPLA": "Cipla",
    "EICHERMOT": "Eicher Motors", "GRASIM": "Grasim", "BPCL": "Bharat Petroleum",
    "DIVISLAB": "Divis Laboratories", "BRITANNIA": "Britannia", "HEROMOTOCO": "Hero MotoCorp",
    "APOLLOHOSP": "Apollo Hospitals", "TATACONSUM": "Tata Consumer", "SBILIFE": "SBI Life",
    "HDFCLIFE": "HDFC Life", "BANKBARODA": "Bank of Baroda", "PNB": "Punjab National Bank",
    "VEDL": "Vedanta", "DLF": "DLF", "HAL": "Hindustan Aeronautics", "BEL": "Bharat Electronics",
    "TRENT": "Trent", "IRCTC": "IRCTC", "JIOFIN": "Jio Financial Services",
}

_full: dict[str, str] = {}
_lock = threading.Lock()
EQUITY_URL = "https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv"


def load_full_universe() -> int:
    """Try to download the NSE equity list (series EQ). Returns count, 0 if unavailable."""
    try:
        r = requests.get(EQUITY_URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
        r.raise_for_status()
        reader = csv.DictReader(io.StringIO(r.text))
        found: dict[str, str] = {}
        for row in reader:
            row = {k.strip(): (v or "").strip() for k, v in row.items() if k}
            if row.get("SERIES") == "EQ" and row.get("SYMBOL"):
                found[row["SYMBOL"]] = row.get("NAME OF COMPANY", row["SYMBOL"])
        with _lock:
            _full.update(found)
        return len(found)
    except Exception:
        return 0


def all_stocks() -> dict[str, str]:
    with _lock:
        merged = dict(_full)
    merged.update(CORE)
    return merged


def search(q: str, limit: int = 30) -> list[dict]:
    q = q.strip().lower()
    stocks = all_stocks()
    if not q:
        return [{"symbol": s, "name": n} for s, n in list(CORE.items())[:limit]]
    starts, contains = [], []
    for s, n in stocks.items():
        sl, nl = s.lower(), n.lower()
        if sl.startswith(q) or nl.startswith(q):
            starts.append({"symbol": s, "name": n})
        elif q in sl or q in nl:
            contains.append({"symbol": s, "name": n})
    return (starts + contains)[:limit]


def name_of(symbol: str) -> Optional[str]:
    return all_stocks().get(symbol)
