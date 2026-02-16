import threading
import logging
from PySide6.QtCore import QObject, Signal

from core.event_bus import bus
from core.playwright_worker import PlaywrightWorker
from core.execution_engine import ExecutionEngine
from core.config_loader import load_secure_config
from core.money_management import MoneyManager
from core.ai_parser import AISignalParser
from core.auto_mapper_worker import AutoMapperWorker
from core.config_paths import HISTORY_FILE


class SuperAgentController(QObject):
    log_message = Signal(str)

    def __init__(self, logger, config=None):
        super().__init__()
        self.logger = logger
        self.config = config or {}

        self._lock = threading.Lock()
        self._active_threads = 0
        self.max_threads = 3

        self.secrets = load_secure_config()
        self.money_manager = MoneyManager()
        self.ai_parser = AISignalParser(api_key=self.secrets.get("openrouter_api_key"))

        self.worker = PlaywrightWorker(logger)
        self.engine = ExecutionEngine(bus, self.worker.executor)

        bus.subscribe("BET_SUCCESS", self._on_bet_success)
        bus.subscribe("BET_FAILED", self._on_bet_failed)
        bus.subscribe("STATE_CHANGE", lambda s: self.logger.info(f"Stato: {s}"))

    def handle_telegram_signal(self, text):
        """Fix Critical: Usa il worker.submit per evitare race conditions."""
        with self._lock:
            if self._active_threads >= self.max_threads:
                self.logger.warning("Too many active threads, skipping signal.")
                return
            self._active_threads += 1

        self.worker.submit(self._process_signal_thread, text)

    def _process_signal_thread(self, text):
        try:
            self.log_message.emit("Analyzing signal...")
            data = self.ai_parser.parse(text)
            if data.get("teams"):
                self.engine.executor = self.worker.executor
                self.engine.process_signal(data, self.money_manager)
        except Exception as e:
            self.logger.error(f"Process error: {e}")
        finally:
            with self._lock:
                self._active_threads -= 1

    def request_auto_mapping(self, url):
        """Fix Critical: Serializza l'automapper nel worker."""
        self.log_message.emit(f"Auto-Discovery started for {url}...")

        self.mapper = AutoMapperWorker(self.worker.executor, url)
        self.mapper.log.connect(self.log_message.emit)
        self.mapper.finished.connect(self._on_mapping_done)

        self.worker.submit(self.mapper.run)

    def _on_mapping_done(self, selectors):
        if selectors:
            self.log_message.emit(f"Mapping OK! Found: {list(selectors.keys())}")
        else:
            self.log_message.emit("Mapping failed.")

    def _on_bet_success(self, payload):
        """Fix Critical: Ripristina logica MoneyManagement e Storico."""
        try:
            if isinstance(payload, str):
                self.log_message.emit(f"WIN: {payload}")
                return

            stake = float(payload.get("stake", 0))
            odds = float(payload.get("odds", 0))

            if self.money_manager:
                self.money_manager.record_outcome("win", stake, odds)
                new_bal = self.money_manager.get_bankroll()
                self.log_message.emit(f"Bankroll updated: {new_bal:.2f}")

            self.log_message.emit(f"WIN recorded: {stake} @ {odds}")

        except Exception as e:
            self.logger.error(f"Error updating win: {e}")
            self.log_message.emit(f"WIN (data error): {payload}")

    # --- STUBS & UTILS ---
    def start_system(self):
        self.logger.info("System Ready (V7.3 Enterprise Fixed).")

    def shutdown(self):
        self.worker.stop()

    def _on_bet_failed(self, e):
        self.log_message.emit(f"FAIL: {e}")

    def set_executor(self, e):
        pass

    def reload_secrets(self):
        self.secrets = load_secure_config()

    def process_robot_chat(self, n, t):
        pass

    def set_live_mode(self, e):
        self.worker.executor.set_live_mode(e)

    def reload_money_manager(self):
        self.money_manager.reload()
