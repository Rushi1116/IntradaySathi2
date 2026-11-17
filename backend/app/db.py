import json
import sqlite3
from contextlib import contextmanager
from typing import Any, Optional

from .config import DB_PATH, INITIAL_BALANCE

SCHEMA = """
CREATE TABLE IF NOT EXISTS account(id INTEGER PRIMARY KEY CHECK(id=1), cash REAL NOT NULL);
CREATE TABLE IF NOT EXISTS trades(
  id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT, side TEXT, qty INTEGER, entry REAL,
  stop_loss REAL, target REAL, interval TEXT, source TEXT, status TEXT, opened_at TEXT,
  closed_at TEXT, exit_price REAL, pnl REAL, exit_reason TEXT, features TEXT, model_version TEXT);
CREATE TABLE IF NOT EXISTS model_versions(
  id INTEGER PRIMARY KEY AUTOINCREMENT, interval TEXT, version TEXT, path TEXT, accuracy REAL,
  samples INTEGER, created_at TEXT, active INTEGER DEFAULT 0, notes TEXT);
CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT);
"""


@contextmanager
def conn():
    c = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=30)
    c.row_factory = sqlite3.Row
    try:
        yield c
        c.commit()
    finally:
        c.close()


def init_db() -> None:
    with conn() as c:
        c.executescript(SCHEMA)
        c.execute("INSERT OR IGNORE INTO account(id, cash) VALUES(1, ?)", (INITIAL_BALANCE,))


def rows(sql: str, args: tuple = ()) -> list[dict]:
    with conn() as c:
        return [dict(r) for r in c.execute(sql, args).fetchall()]


def execute(sql: str, args: tuple = ()) -> int:
    with conn() as c:
        return c.execute(sql, args).lastrowid


def get_setting(key: str, default: Any = None) -> Any:
    r = rows("SELECT value FROM settings WHERE key=?", (key,))
    return json.loads(r[0]["value"]) if r else default


def set_setting(key: str, value: Any) -> None:
    execute("INSERT OR REPLACE INTO settings(key, value) VALUES(?, ?)", (key, json.dumps(value)))


def get_cash() -> float:
    return float(rows("SELECT cash FROM account WHERE id=1")[0]["cash"])


def set_cash(v: float) -> None:
    execute("UPDATE account SET cash=? WHERE id=1", (round(v, 2),))
