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
from core.dom_executor_playwright import DomExecutorPlaywright

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
        # Inizializza l'executor e lo assegna al worker
        self.worker.executor = DomExecutorPlaywright(logger=logger, headless=False)
        self.engine = ExecutionEngine(bus, self.worker.executor)
        
        bus.subscribe("BET_SUCCESS", self._on_bet_success)
        bus.subscribe("BET_FAILED", self._on_bet_failed)

    def handle_telegram_signal(self, text):
        with self._lock:
            if self._active_threads >= self.max_threads:
                self.logger.warning("⚠️ Troppi thread attivi, ignoro segnale.")
                return
            self._active_threads += 1

        self.worker.submit(self._process_signal_thread, text)

    def _process_signal_thread(self, text):
        try:
            self.log_message.emit("📩 Analisi segnale...")
            data = self.ai_parser.parse(text)
            if data.get("teams"):
                self.engine.process_signal(data, self.money_manager)
        except Exception as e:
            self.logger.error(f"Process error: {e}")
        finally:
            with self._lock:
                self._active_threads -= 1

    def request_auto_mapping(self, url):
        self.log_message.emit(f"🕵️ Mapping {url}...")
        self.mapper = AutoMapperWorker(self.worker.executor, url)
        self.mapper.log.connect(self.log_message.emit)
        self.mapper.finished.connect(self._on_mapping_done)
        self.worker.submit(self.mapper.run)

    def _on_mapping_done(self, selectors):
        # Qui integriamo la logica di auto-mapping che salva il file
        self.log_message.emit(f"✅ Scansione completata. Trovati {len(selectors)} elementi candidati.")
        
        new_selectors = {}
        for el in selectors:
            txt = el.lower()
            if "input" in txt and ("stake" in txt or "amount" in txt):
                new_selectors["stake_input"] = self._extract_css(el)
            elif "button" in txt and ("scommetti" in txt or "place" in txt):
                new_selectors["place_button"] = self._extract_css(el)
            elif "button" in txt and ("accedi" in txt or "login" in txt):
                new_selectors["login_button"] = self._extract_css(el)

        if new_selectors:
            import yaml
            import os
            from core.config_paths import CONFIG_DIR
            path = os.path.join(CONFIG_DIR, "selectors_discovered.yaml")
            try:
                with open(path, "w") as f:
                    yaml.dump(new_selectors, f)
                self.log_message.emit(f"💾 Selettori salvati in: {path}")
            except Exception as e:
                self.logger.error(f"Errore salvataggio mapping: {e}")
        else:
            self.log_message.emit("❌ Nessun selettore chiave identificato automaticamente.")

    def _extract_css(self, element_string):
        try:
            parts = element_string.split("| Class:")
            if len(parts) > 1:
                cls = parts[1].strip()
                if cls: return f".{cls.split()[0]}"
        except: pass
        return "SELETTORE_NON_TROVATO"

    def _on_bet_success(self, payload):
        try:
            stake = float(payload.get("stake", 0))
            odds = float(payload.get("odds", 0))
            
            if self.money_manager:
                self.money_manager.record_outcome("win", stake, odds)
                bal = self.money_manager.get_bankroll()
                self.log_message.emit(f"💰 WIN! Nuovo saldo: {bal:.2f}€")
            else:
                self.log_message.emit(f"WIN: {payload}")
        except Exception as e:
            self.logger.error(f"Err bet success handler: {e}")

    def start_system(self): 
        self.logger.info("System Ready V7.4 Enterprise")

    def shutdown(self): 
        self.worker.stop()

    def _on_bet_failed(self, e): 
        self.log_message.emit(f"FAIL: {e}")

    def set_live_mode(self, e):
        if self.worker.executor:
            self.worker.executor.set_live_mode(e)

    def reload_money_manager(self): 
        self.money_manager.reload()