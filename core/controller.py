import threading
import logging
import time
import json
import os
from PySide6.QtCore import QObject, Signal

from core.event_bus import bus
from core.playwright_worker import PlaywrightWorker
from core.execution_engine import ExecutionEngine
from core.money_management import MoneyManager
from core.dom_executor_playwright import DomExecutorPlaywright
from core.config_paths import CONFIG_DIR


STATE_FILE = os.path.join(CONFIG_DIR, "runtime_state.json")


class SuperAgentController(QObject):
    log_message = Signal(str)

    def __init__(self, logger):
        super().__init__()
        self.logger = logger
        self.money_manager = MoneyManager()

        self.worker = PlaywrightWorker(logger)
        self.worker.executor = DomExecutorPlaywright(logger=logger)

        self.engine = ExecutionEngine(bus, self.worker.executor)

        self.fail_count = 0
        self.circuit_open = False
        self._lock = threading.Lock()
        self._last_signal_time = 0

        self._load_state()

        bus.subscribe("BET_SUCCESS", self._on_bet_success)
        bus.subscribe("BET_FAILED", self._on_bet_failed)

        self.worker.start()
        bus.start()

        threading.Thread(
            target=self._browser_watchdog,
            daemon=True
        ).start()

    # 🔥 Persistenza runtime
    def _save_state(self):
        try:
            os.makedirs(CONFIG_DIR, exist_ok=True)
            with open(STATE_FILE, "w") as f:
                json.dump({
                    "fail_count": self.fail_count,
                    "circuit_open": self.circuit_open
                }, f)
        except Exception:
            pass

    def _load_state(self):
        try:
            if os.path.exists(STATE_FILE):
                with open(STATE_FILE) as f:
                    data = json.load(f)
                    self.fail_count = data.get("fail_count", 0)
                    self.circuit_open = data.get("circuit_open", False)
        except Exception:
            pass

    # 🔥 Watchdog SAFE
    def _browser_watchdog(self):
        while True:
            time.sleep(10)
            ex = self.worker.executor
            if ex and getattr(ex, "page", None):
                try:
                    if ex.page.is_closed():
                        self.logger.warning("Watchdog restart browser")
                        ex.recycle_browser()
                except Exception:
                    pass

    # 🔥 Rate limit 1 segnale / sec
    def handle_signal(self, data):
        if self.circuit_open:
            self.logger.warning("Circuit open. Signal ignored.")
            return

        now = time.time()
        if now - self._last_signal_time < 1:
            return
        self._last_signal_time = now

        self.worker.submit(
            self.engine.process_signal,
            data,
            self.money_manager
        )

    def _on_bet_success(self, payload):
        with self._lock:
            self.fail_count = 0
            self.circuit_open = False
            self._save_state()

        try:
            stake = float(payload.get("stake", 0))
            odds = float(payload.get("odds", 0))
            self.money_manager.record_outcome("win", stake, odds)
            bal = self.money_manager.get_bankroll()
            self.log_message.emit(f"💰 WIN | Saldo: {bal:.2f}€")
        except Exception as e:
            self.logger.error(f"Success handler error: {e}")

    def _on_bet_failed(self, payload):
        with self._lock:
            self.fail_count += 1
            self.log_message.emit(f"FAIL #{self.fail_count}")

            if self.fail_count >= 3:
                self.logger.critical("🚨 CIRCUIT BREAKER TRIGGERED")
                self.circuit_open = True
                self.worker.stop()

            self._save_state()