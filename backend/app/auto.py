import threading
import time
import traceback
from collections import deque
from typing import Optional

from . import db, ml, paper
from .config import (AUTO_INTERVAL_SECONDS, DAILY_LOSS_LIMIT, ENFORCE_MARKET_HOURS, MAX_OPEN_POSITIONS,
                     MAX_TRADES_PER_DAY, MIN_CONFIDENCE, entry_window, now_ist)
from .universe import CORE


def default_cfg() -> dict:
    return {"daily_loss_limit": DAILY_LOSS_LIMIT, "max_trades": MAX_TRADES_PER_DAY,
            "min_confidence": MIN_CONFIDENCE, "max_open": MAX_OPEN_POSITIONS,
            "interval": "5m", "watchlist": list(CORE.keys())[:10]}


class AutoTrader:
    def __init__(self) -> None:
        self.status = "stopped"  # stopped | running | paused | emergency
        self.halt_reason: Optional[str] = None
        self.log: deque = deque(maxlen=60)
        self.last_run: Optional[str] = None
        self.last_retrain_day: Optional[str] = None
        self.lock = threading.Lock()
        self.thread: Optional[threading.Thread] = None

    @property
    def cfg(self) -> dict:
        c = default_cfg()
        c.update(db.get_setting("auto_cfg", {}))
        return c

    def set_cfg(self, new: dict) -> dict:
        c = self.cfg
        for k in ("daily_loss_limit", "min_confidence"):
            if k in new and new[k] is not None:
                c[k] = float(new[k])
        for k in ("max_trades", "max_open"):
            if k in new and new[k] is not None:
                c[k] = int(new[k])
        if new.get("interval") in ("5m", "15m"):
            c["interval"] = new["interval"]
        if new.get("watchlist"):
            c["watchlist"] = [s.upper().strip() for s in new["watchlist"]][:25]
        if not (0.34 <= c["min_confidence"] <= 0.99):
            raise ValueError("min_confidence must be between 0.34 and 0.99")
        if c["daily_loss_limit"] <= 0 or c["max_trades"] < 1 or c["max_open"] < 1:
            raise ValueError("limits must be positive")
        db.set_setting("auto_cfg", c)
        return c

    def say(self, msg: str) -> None:
        self.log.appendleft(f"{now_ist().strftime('%H:%M:%S')} {msg}")

    def start(self) -> None:
        with self.lock:
            if self.status == "emergency":
                raise ValueError("Emergency stop active. Press Stop to reset before starting.")
            self.status, self.halt_reason = "running", None
            self.say("Started")

    def pause(self) -> None:
        with self.lock:
            if self.status != "running":
                raise ValueError("Not running")
            self.status = "paused"
            self.say("Paused (open positions are still monitored)")

    def resume(self) -> None:
        with self.lock:
            if self.status != "paused":
                raise ValueError("Not paused")
            self.status, self.halt_reason = "running", None
            self.say("Resumed")

    def stop(self) -> None:
        with self.lock:
            self.status, self.halt_reason = "stopped", None
            self.say("Stopped (open positions are still monitored)")

    def emergency_stop(self) -> int:
        with self.lock:
            self.status = "emergency"
            n = paper.close_all("emergency_stop")
            self.say(f"EMERGENCY STOP: closed {n} positions")
            return n

    def snapshot(self) -> dict:
        p = paper.portfolio()
        return {"status": self.status, "halt_reason": self.halt_reason, "config": self.cfg,
                "last_run": self.last_run, "trades_today": paper.trades_today("auto"),
                "open_positions": len(p["positions"]), "today_pnl": p["today_pnl"],
                "market_open": ENFORCE_MARKET_HOURS is False or entry_window(), "log": list(self.log)}

    def tick(self) -> None:
        self.last_run = now_ist().isoformat()
        for t in paper.monitor():
            self.say(f"Closed {t['symbol']} {t['exit_reason']} pnl={t['pnl']}")
        self.maybe_retrain()
        if self.status != "running":
            return
        cfg = self.cfg
        if ENFORCE_MARKET_HOURS and not entry_window():
            return
        p = paper.portfolio()
        if p["today_pnl"] <= -cfg["daily_loss_limit"]:
            self.status, self.halt_reason = "paused", "Daily loss limit reached"
            self.say("Daily loss limit reached: paused, no new entries")
            return
        if paper.trades_today("auto") >= cfg["max_trades"]:
            return
        if len(p["positions"]) >= cfg["max_open"]:
            return
        held = {x["symbol"] for x in p["positions"]}
        for sym in cfg["watchlist"]:
            if sym in held or self.status != "running":
                continue
            try:
                s = ml.predict(sym, cfg["interval"])
            except Exception:
                continue
            if s["signal"] == "HOLD" or s["confidence"] < cfg["min_confidence"] or s["model_type"] != "xgboost":
                continue
            side = s["signal"]
            lv = s["levels"][side.lower()]
            price, risk = s["price"], s["risk_per_share"]
            equity, cash = p["equity"], db.get_cash()
            qty = int(min(equity * 0.01 / risk, equity * 0.25 / price, cash / price))
            if qty < 1:
                continue
            try:
                t = paper.place_order(sym, side, qty, lv["stop_loss"], lv["target"], cfg["interval"], "auto",
                                      s["features"], s["model_version"], price)
                self.say(f"{side} {qty} {sym} @ {price} conf={s['confidence']:.2f}")
                held.add(sym)
            except ValueError as e:
                self.say(f"Skip {sym}: {e}")
                continue
            if paper.trades_today("auto") >= cfg["max_trades"] or len(held) >= cfg["max_open"]:
                break

    def maybe_retrain(self) -> None:
        n = now_ist()
        day = n.strftime("%Y-%m-%d")
        if n.weekday() < 5 and (n.hour, n.minute) >= (15, 45) and self.last_retrain_day != day:
            self.last_retrain_day = day
            for iv in ("5m", "15m"):
                try:
                    r = ml.retrain_if_ready(iv)
                    if r.get("retrained"):
                        self.say(f"Retrained {iv}: {r['version']} activated={r['activated']}")
                except Exception as e:
                    self.say(f"Retrain {iv} failed: {e}")

    def loop(self) -> None:
        while True:
            try:
                self.tick()
            except Exception:
                self.say("Tick error: " + traceback.format_exc().splitlines()[-1])
            time.sleep(AUTO_INTERVAL_SECONDS)

    def ensure_thread(self) -> None:
        if self.thread is None or not self.thread.is_alive():
            self.thread = threading.Thread(target=self.loop, daemon=True, name="auto-trader")
            self.thread.start()


trader = AutoTrader()
