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
from core.config_paths import HISTORY_FILE  # Import centralizzato


class SuperAgentController(QObject):
    log_message = Signal(str)

    def __init__(self, logger, config=None):
        super().__init__()
        self.logger = logger
        self.config = config or {}

        self._lock = threading.Lock()
        self._active_threads = 0
        self.max_threads = 3  # Limite sicurezza

        self.secrets = load_secure_config()
        self.money_manager = MoneyManager()
        self.ai_parser = AISignalParser(api_key=self.secrets.get("openrouter_api_key"))

        self.worker = None
        self.engine = None

        bus.subscribe("BET_SUCCESS", self._on_bet_success)
        bus.subscribe("BET_FAILED", self._on_bet_failed)
        bus.subscribe("STATE_CHANGE", lambda s: self.logger.info(f"Stato: {s}"))

    def set_executor(self, executor):
        self.worker = PlaywrightWorker(executor, self.logger)
        self.engine = ExecutionEngine(bus, self.worker.executor)

    def handle_telegram_signal(self, text):
        """Fix Medium #3: Race Condition risolta con Lock."""
        with self._lock:
            if self._active_threads >= self.max_threads:
                self.logger.warning("Too many active threads, skipping signal.")
                return
            self._active_threads += 1

        threading.Thread(target=self._process_signal_thread, args=(text,), daemon=True).start()

    def _process_signal_thread(self, text):
        try:
            self.log_message.emit("Analyzing signal...")
            data = self.ai_parser.parse(text)
            if data.get("teams"):
                self.engine.process_signal(data, self.money_manager)
        except Exception as e:
            self.logger.error(f"Process error: {e}")
        finally:
            with self._lock:
                self._active_threads -= 1

    # --- AUTO MAPPING ---
    def request_auto_mapping(self, url):
        self.log_message.emit(f"Auto-Discovery started for {url}...")
        self.mapper = AutoMapperWorker(self.worker.executor, url)
        self.mapper.log.connect(self.log_message.emit)
        self.mapper.finished.connect(self._on_mapping_done)
        threading.Thread(target=self.mapper.run, daemon=True).start()

    def _on_mapping_done(self, selectors):
        if selectors:
            self.log_message.emit(f"Mapping OK! Found: {list(selectors.keys())}")
        else:
            self.log_message.emit("Mapping failed.")

    # --- STUBS & UTILS ---
    def start_system(self):
        self.logger.info("System Ready (V7.3 Enterprise).")

    def shutdown(self):
        if self.worker:
            self.worker.stop()

    def _on_bet_success(self, p):
        self.log_message.emit(f"WIN: {p}")

    def _on_bet_failed(self, e):
        self.log_message.emit(f"FAIL: {e}")

    def reload_secrets(self):
        self.secrets = load_secure_config()

    def process_robot_chat(self, n, t):
        pass

    def set_live_mode(self, enabled):
        if self.worker and self.worker.executor:
            self.worker.executor.set_live_mode(enabled)

    def reload_money_manager(self):
        self.money_manager.reload()
