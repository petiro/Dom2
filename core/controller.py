import threading
import logging
import json
import os
import time
from datetime import datetime
from PySide6.QtCore import QObject, Signal, QThread

# Import Core
from core.money_management import MoneyManager
from core.ai_parser import AISignalParser
from core.config_loader import load_secure_config
from core.security import Vault
from core.state_machine import StateManager, AgentState
from core.auto_mapper_worker import AutoMapperWorker
from core.arch_v6 import PlaywrightWorker, SessionGuardian, PlaywrightWatchdog, EventBusV6
from core.execution_engine import ExecutionEngine
from core.event_bus import bus

# Import opzionale per compatibilita
try:
    from core.signal_parser import TelegramSignalParser
except Exception:
    TelegramSignalParser = None

try:
    from core.telegram_worker import TelegramWorker
except Exception:
    TelegramWorker = None

_ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HISTORY_FILE = os.path.join(_ROOT_DIR, "config", "bet_history.json")
SELECTORS_FILE = os.path.join(_ROOT_DIR, "config", "selectors.yaml")


class SuperAgentController(QObject):
    log_message = Signal(str)
    mapping_ready = Signal(str)  # FIX BUG-02: Signal per UI Mapping

    def __init__(self, logger_instance, config=None):
        super().__init__()
        self.logger = logger_instance
        self.config = config or {}

        # --- 1. Sicurezza & Stato (FIX BUG-02/11) ---
        self.vault = Vault()
        self.state_manager = StateManager(self.logger, initial_state=AgentState.BOOT)

        # --- 2. Caricamento Chiavi ---
        self.secrets = load_secure_config()
        api_key = self.secrets.get("openrouter_api_key")

        if not api_key:
            self.logger.warning("⚠️ Controller: Chiave AI mancante. Funzionalita limitate.")
        else:
            self.logger.info("🔑 Chiavi API caricate.")

        # --- 3. Componenti ---
        self.ai_parser = AISignalParser(api_key=api_key)
        self.money_manager = MoneyManager()
        self.legacy_parser = TelegramSignalParser() if TelegramSignalParser else None

        # Placeholder componenti esterni
        self.executor = None
        self.trainer = None
        self.monitor = None
        self.watchdog = None
        self.command_parser = None
        self.ui_window = None

        # V6 Architecture
        self.pw_worker = None
        self.session_guardian = None
        self.pw_watchdog = None
        self.event_bus = EventBusV6(logger_instance)

        # Workers
        self.mapper_worker = None
        self.mapper_thread = None
        self.telegram_worker = None

        # Threading
        self._history = self._load_history()
        self._lock = threading.Lock()
        self._active_threads = 0

    # --- SETUP & CONNESSIONI ---
    def set_executor(self, ex):
        self.executor = ex
        # V6: Inizializza Worker, Guardian, Watchdog
        self.pw_worker = PlaywrightWorker(self.executor, self.logger)
        self.session_guardian = SessionGuardian(self.executor, self.logger)
        self.pw_watchdog = PlaywrightWatchdog(self.pw_worker, self.logger)
        # V7: ExecutionEngine event-driven
        self.execution_engine = ExecutionEngine(self.executor, self.pw_worker, self.logger)
        bus.subscribe("BET_SUCCESS", self._on_bet_success)
        bus.subscribe("BET_FAILED", self._on_bet_failed)

    def set_trainer(self, trainer):
        self.trainer = trainer
        if self.trainer and self.executor:
            self.trainer.set_executor(self.executor)

    def set_monitor(self, monitor):
        self.monitor = monitor

    def set_watchdog(self, watchdog):
        self.watchdog = watchdog

    def set_command_parser(self, parser):
        self.command_parser = parser

    def start_system(self):
        self.logger.info("Avvio Sistema V6...")
        self.state_manager.transition(AgentState.IDLE)
        # V6: Avvia Guardian e Watchdog
        if self.session_guardian:
            self.session_guardian.start()
        else:
            self.logger.warning(
                "SessionGuardian non inizializzato: chiamare set_executor "
                "prima di start_system per abilitare la protezione V6."
            )
        if self.pw_watchdog:
            self.pw_watchdog.start()
        else:
            self.logger.warning(
                "PlaywrightWatchdog non inizializzato: chiamare set_executor "
                "prima di start_system per abilitare il watchdog V6."
            )
        self.logger.info("Controller V6 avviato. State: IDLE.")

    # --- TELEGRAM INTEGRATION (FIX BUG-04) ---
    def connect_telegram(self, tg_config):
        """Metodo chiamato dalla TelegramTab per connettere Telegram."""
        if TelegramWorker is None:
            self.logger.error("❌ TelegramWorker non disponibile (telethon mancante)")
            return

        self.logger.info("📡 Connessione Telegram avviata...")
        if self.telegram_worker:
            self.telegram_worker.stop()

        self.telegram_worker = TelegramWorker(tg_config)
        self.telegram_worker.message_received.connect(self.handle_telegram_signal)
        self.telegram_worker.error_occurred.connect(
            lambda e: self.logger.error(f"Telegram Error: {e}"))
        self.telegram_worker.status_changed.connect(
            lambda s: self.logger.info(f"Telegram Status: {s}"))
        self.telegram_worker.start()

    # --- AUTO MAPPING (FIX BUG-02) ---
    def request_auto_mapping(self, url):
        """Avvia il mapping AI dei selettori per un URL."""
        self.logger.info(f"🗺️ Mapping richiesto per: {url}")

        dom_content = ""
        if self.executor:
            self.logger.info("Recupero DOM dal browser...")
            dom_content = self.executor.get_dom_snapshot()

        if not dom_content:
            dom_content = f"<html><body>URL target: {url} - Browser non attivo</body></html>"

        api_key = self.secrets.get("openrouter_api_key")
        if not api_key:
            self.logger.error("❌ Mapping impossibile: Manca API Key OpenRouter")
            return

        self.mapper_thread = QThread()
        self.mapper_worker = AutoMapperWorker(api_key, dom_content)
        self.mapper_worker.moveToThread(self.mapper_thread)

        self.mapper_worker.finished.connect(self._on_mapping_success)
        self.mapper_worker.error.connect(lambda e: self.logger.error(f"Mapper Error: {e}"))
        self.mapper_worker.finished.connect(self.mapper_thread.quit)
        self.mapper_thread.started.connect(self.mapper_worker.run)

        self.mapper_thread.start()

    def _on_mapping_success(self, result):
        import yaml
        yaml_str = yaml.dump(result, default_flow_style=False)
        self.mapping_ready.emit(yaml_str)
        self.logger.info("✅ Mapping completato!")

    def save_selectors_yaml(self, yaml_content):
        """Salva i selettori YAML su file. Chiamato dalla MappingTab."""
        try:
            os.makedirs(os.path.dirname(SELECTORS_FILE), exist_ok=True)
            with open(SELECTORS_FILE, "w", encoding="utf-8") as f:
                f.write(yaml_content)
            self.logger.info("💾 Selettori salvati su file.")
        except Exception as e:
            self.logger.error(f"Errore salvataggio YAML: {e}")

    # --- LOGICA OPERATIVA ---
    def set_live_mode(self, enabled):
        if self.executor:
            self.executor.set_live_mode(enabled)

    def reload_money_manager(self):
        self.money_manager.reload()
        self.logger.info("💰 Money Manager ricaricato.")

    def reload_secrets(self):
        """Metodo chiamato dalla UI quando si salvano nuove chiavi."""
        self.secrets = load_secure_config()
        api_key = self.secrets.get("openrouter_api_key")
        if self.ai_parser:
            self.ai_parser.api_key = api_key
        self.logger.info("🔑 Secrets ricaricati.")

    def handle_telegram_signal(self, text):
        """V6: Invia il lavoro al Worker (NON BLOCCA GUI)."""
        # Protezione watchdog comune a worker e fallback
        with self._lock:
            if self._active_threads > 2:
                self.logger.warning("Watchdog: Troppi thread attivi. Skip.")
                return
            self._active_threads += 1
        if self.pw_worker:
            self.pw_worker.submit(self._process_signal_thread, text)
        else:
            # Fallback: thread diretto
            threading.Thread(
                target=self._process_signal_thread, args=(text,), daemon=True
            ).start()

    def _process_signal_thread(self, text):
        try:
            self.state_manager.set_state(AgentState.ANALYZING)
            self.logger.info("📩 Analisi segnale...")

            # 1. Prova AI Parser
            data = self.ai_parser.parse(text)

            # 2. Fallback su Parser classico (FIX BUG-01: ora usa "teams")
            if (not data or not data.get("teams")) and self.legacy_parser:
                self.logger.info("🤖 Fallback su parser classico...")
                data = self.legacy_parser.parse(text)

            if not data or not data.get("teams"):
                self.logger.warning("⚠️ Dati insufficienti.")
                return

            teams = data.get("teams", "")
            market = data.get("market", "")
            self.logger.info(f"🎯 Target: {teams} -> {market}")

            # FIX BUG-09: Usa CommandParser se disponibile
            if self.command_parser:
                steps = self.command_parser.parse(data)
                self.logger.info(f"📋 Pipeline: {len(steps)} steps generati")

            self.execution_engine.process_signal(data, self.money_manager)

        except Exception as e:
            self.logger.error(f"❌ Errore process signal: {e}")
        finally:
            with self._lock:
                self._active_threads -= 1
            self.state_manager.set_state(AgentState.IDLE)

    def _on_bet_success(self, payload):
        """Handler evento BET_SUCCESS da ExecutionEngine."""
        data = payload.get("data", {})
        stake = payload.get("stake", 0)
        odds = payload.get("odds", 0)
        teams = data.get("teams", "")
        market = data.get("market", "")

        record = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "teams": teams,
            "market": market,
            "stake": stake,
            "odds": odds,
            "status": "CONFERMATA"
        }
        self._save_to_history(record)
        self.money_manager.record_outcome("win", stake, odds)

        msg = f"BET: {stake}$ su {teams} ({market})"
        self.logger.info(msg)
        self.safe_emit(msg)

    def _on_bet_failed(self, reason):
        """Handler evento BET_FAILED da ExecutionEngine."""
        self.logger.warning(f"BET FAILED: {reason}")
        self.state_manager.set_state(AgentState.ERROR)

    def _load_history(self):
        if os.path.exists(HISTORY_FILE):
            try:
                with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                return []
        return []

    def _save_to_history(self, record):
        with self._lock:
            self._history.append(record)
            try:
                with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
                    json.dump(self._history, f, indent=4)
            except Exception as e:
                self.logger.error(f"Errore salvataggio history: {e}")

    def get_bet_history(self):
        with self._lock:
            return list(self._history)

    def safe_emit(self, msg):
        try:
            self.log_message.emit(msg)
        except Exception:
            pass

    # --- STUBS RICHIESTI DALLA UI ---
    def shutdown(self):
        self.logger.info("Shutdown V6...")
        self.state_manager.set_state(AgentState.SHUTDOWN)
        # V6: Ferma monitor prima, poi worker
        if self.pw_watchdog:
            self.pw_watchdog.stop()
        if self.session_guardian:
            self.session_guardian.stop()
        if self.pw_worker:
            self.pw_worker.stop()
        if self.event_bus:
            self.event_bus.stop()
        bus.stop()
        if self.executor:
            self.executor.close()
        if self.telegram_worker:
            self.telegram_worker.stop()

    def request_training(self):
        pass

    def process_robot_chat(self, robot_name, text):
        self.logger.info(f"💬 Chat robot {robot_name}: {text}")
        if self.ui_window and hasattr(self.ui_window, 'factory'):
            try:
                self.ui_window.factory.receive_ai_reply(robot_name, "Ricevuto. Sto imparando...")
            except Exception as e:
                self.logger.error(f"Errore invio reply a UI: {e}")
