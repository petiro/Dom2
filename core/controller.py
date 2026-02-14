import time
import threading
import logging
import yaml
import os
from PySide6.QtCore import QObject, Signal
from core.state_machine import AgentState, StateManager
from core.signal_parser import TelegramSignalParser
from core.security import Vault
from core.config_loader import load_secure_config

logger = logging.getLogger("SuperAgent")

class SuperAgentController(QObject):
    log_message = Signal(str)
    training_complete = Signal(str)
    mapping_ready = Signal(str)

    def __init__(self, logger_instance=None, config=None):
        super().__init__()
        self.logger = logger_instance or logger
        self.config = load_secure_config() or config or {}
        
        self.vault = Vault()
        try:
            secrets = self.vault.decrypt_data()
            if secrets: self._merge_secrets(secrets)
        except Exception: pass

        self._executor_lock = threading.RLock()
        self._data_lock = threading.Lock()

        self.executor = None
        self.trainer = None
        self.monitor = None
        self._bet_results = []
        
        self.parser = TelegramSignalParser()
        self.state_manager = StateManager(self.logger, initial_state=AgentState.BOOT)

    def _merge_secrets(self, secrets):
        if "telegram" in secrets:
            if "telegram" not in self.config: self.config["telegram"] = {}
            self.config["telegram"].update(secrets["telegram"])
        if "openrouter_api_key" in secrets:
            self.config["api_key"] = secrets["openrouter_api_key"]
        if "pin" in secrets:
            self.config["pin"] = secrets["pin"]

    def set_executor(self, ex):
        with self._executor_lock:
            self.executor = ex
            if self.executor and "pin" in self.config:
                self.executor.pin = self.config["pin"]

    # --- NUOVO METODO PER IL LIVE MODE ---
    def set_live_mode(self, enabled: bool):
        """Attiva o disattiva la modalità scommessa reale."""
        with self._executor_lock:
            if self.executor:
                self.executor.set_live_mode(enabled)
                status = "🔴 LIVE (SOLDI VERI)" if enabled else "🟢 DEMO (Simulazione)"
                self.logger.info(f"Modalità operativa cambiata: {status}")
                self.safe_emit(self.log_message, f"Modalità cambiata: {status}")

    def start_system(self):
        self.state_manager.transition(AgentState.IDLE)
        self.safe_emit(self.log_message, "✅ Sistema Avviato")

    def handle_telegram_signal(self, text):
        data = self.parser.parse(text)
        if not data.get("teams"): return
        self.logger.info(f"Segnale ricevuto: {data['teams']}")
        threading.Thread(target=self._process_bet_safely, args=(data,), daemon=True).start()

    def _process_bet_safely(self, data):
        with self._executor_lock:
            if not self.executor: return
            selectors = self.executor._load_selectors()
            if self.executor.ensure_login(selectors): 
                if self.executor.navigate_to_match(data["teams"], selectors):
                    # Qui la scommessa parte. Se è LIVE o DEMO lo decide l'executor
                    self.executor.place_bet(data["teams"], data["market"], 1.0)
            with self._data_lock:
                self._bet_results.append(data)

    def shutdown(self):
        self.safe_emit(self.log_message, "Shutdown...")
        with self._executor_lock:
            if self.executor: self.executor.close()

    def safe_emit(self, signal, msg):
        try: signal.emit(msg)
        except: pass
    
    # Stubs
    def set_trainer(self, t): self.trainer = t
    def set_monitor(self, m): self.monitor = m
    def set_watchdog(self, w): pass
    def set_command_parser(self, c): pass
    def request_training(self): pass
    def connect_telegram(self, c): pass
    def request_auto_mapping(self, u): pass
    def save_selectors_yaml(self, y): pass
    def load_robot_profile(self, p): pass
    def get_stats(self): return {"bets_total": len(self._bet_results)}
    def get_bet_history(self): 
        with self._data_lock: return list(self._bet_results)
