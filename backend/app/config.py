import os
from datetime import datetime
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv()

IST = ZoneInfo("Asia/Kolkata")


def _f(name: str, default: str) -> float:
    return float(os.getenv(name, default))


def _i(name: str, default: str) -> int:
    return int(os.getenv(name, default))


INITIAL_BALANCE = _f("INITIAL_BALANCE", "100000")
DB_PATH = os.getenv("DB_PATH", "intraday_sathi.db")
MODEL_DIR = os.getenv("MODEL_DIR", "models")
DAILY_LOSS_LIMIT = _f("DAILY_LOSS_LIMIT", "2000")
MAX_TRADES_PER_DAY = _i("MAX_TRADES_PER_DAY", "10")
MAX_OPEN_POSITIONS = _i("MAX_OPEN_POSITIONS", "3")
MIN_CONFIDENCE = _f("MIN_CONFIDENCE", "0.60")
RETRAIN_MIN_TRADES = _i("RETRAIN_MIN_TRADES", "30")
TRAIN_SYMBOLS = _i("TRAIN_SYMBOLS", "15")
CANDLE_TTL_SECONDS = _i("CANDLE_TTL_SECONDS", "60")
AUTO_INTERVAL_SECONDS = _i("AUTO_INTERVAL_SECONDS", "60")
ENFORCE_MARKET_HOURS = os.getenv("ENFORCE_MARKET_HOURS", "true").lower() == "true"
LOAD_FULL_UNIVERSE = os.getenv("LOAD_FULL_UNIVERSE", "true").lower() == "true"

DISCLAIMER = (
    "Intraday Sathi is a PAPER-TRADING and education tool. It never places real orders. "
    "Market data comes from free public sources (Yahoo Finance) and is typically delayed by about 15 minutes "
    "and may be incomplete or wrong. AI signals come from statistical models trained on limited recent data; "
    "they can be wrong, have no guaranteed accuracy and do not guarantee profit. Past or simulated results do "
    "not predict real results. Paper trading ignores brokerage, taxes, slippage and liquidity. Intraday trading "
    "carries a high risk of loss. This is not investment advice; consult a SEBI-registered adviser."
)


def now_ist() -> datetime:
    return datetime.now(IST)


def market_open() -> bool:
    n = now_ist()
    return n.weekday() < 5 and (9, 15) <= (n.hour, n.minute) < (15, 30)


def entry_window() -> bool:
    """New automated entries only between 09:20 and 15:00 IST."""
    n = now_ist()
    return n.weekday() < 5 and (9, 20) <= (n.hour, n.minute) < (15, 0)
