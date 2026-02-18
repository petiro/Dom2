import logging
import threading
import time
import yaml
import os
import json # FIX APPLICATO: Import necessario per save/load state
from PySide6.QtCore import QObject, Signal

from core.event_bus import bus
from core.playwright_worker import PlaywrightWorker
from core.execution_engine import ExecutionEngine
from core.money_management import MoneyManager
from core.dom_executor_playwright import DomExecutorPlaywright
from core.database import Database
from core.auto_mapper_worker import AutoMapperWorker
from core.dom_self_healing import DOMSelfHealing
from core.multi_site_scanner import MultiSiteScanner
from core.config_paths import CONFIG_DIR

STATE_FILE = os.path.join(CONFIG_DIR, "runtime_state.json")

class SuperAgentController(QObject):
    log_message = Signal(str)

    def __init__(self, logger):
        super().__init__()
        self.logger = logger
        
        self.db = Database()
        self.money_manager = MoneyManager()
        
        self.worker = PlaywrightWorker(logger)
        self.worker.executor = DomExecutorPlaywright(logger=logger)
        self.engine = ExecutionEngine(bus, self.worker.executor)

        self.self_healer = DOMSelfHealing(self.worker.executor)
        self.scanner = MultiSiteScanner(self.worker.executor)
        
        self.fail_count = 0
        self.circuit_open = False
        self._lock = threading.Lock()
        self._last_signal_time = 0

        self._load_state()

        bus.subscribe("BET_SUCCESS", self._on_bet_success)
        bus.subscribe("BET_FAILED", self._on_bet_failed)
        
        self.worker.start()
        bus.start()
        
        threading.Thread(target=self._browser_watchdog, daemon=True).start()
        self._perform_recovery()
        
        self.log_message.emit("✅ SISTEMA V8.4 STABLE AVVIATO")

    def _perform_recovery(self):
        try:
            pending = self.db.pending()
            if pending:
                self.logger.warning(f"Recovery: {len(pending)} transazioni pendenti.")
                for row in pending:
                    self.money_manager.refund(row['tx_id'])
        except Exception as e:
            self.logger.error(f"Recovery error: {e}")

    def start_auto_mapping(self, url):
        self.log_message.emit(f"🧠 AVVIO AUTO-MAPPING: {url}")
        self.mapper = AutoMapperWorker(self.worker.executor, url)
        self.mapper.log.connect(self.log_message.emit)
        self.mapper.finished.connect(self._on_mapping_done)
        self.worker.submit(self.mapper.run)

    def _on_mapping_done(self, selectors):
        if selectors:
            self.log_message.emit(f"✅ MAPPING OK: {len(selectors)} selettori.")
        else:
            self.log_message.emit("❌ MAPPING FALLITO.")

    def scan_multiple_sites(self, url_list):
        self.log_message.emit(f"🌐 Avvio Multi-Scan ({len(url_list)} siti)...")
        self.worker.submit(lambda: self.scanner.scan(url_list))

    def handle_signal(self, data):
        if not self.worker.running: return

        if self.circuit_open:
            self.logger.warning("Circuit Breaker attivo. Ignoro.")
            return

        now = time.time()
        if now - self._last_signal_time < 1.0: return
        self._last_signal_time = now

        self.worker.submit(self.engine.process_signal, data, self.money_manager)

    def _on_bet_success(self, payload):
        with self._lock:
            self.fail_count = 0
            self.circuit_open = False
            self._save_state()
        
        tx_id = payload.get("tx_id")
        if tx_id: self.money_manager.win(tx_id, payload.get("payout", 0))
        self.log_message.emit(f"💰 WIN | Saldo: {self.money_manager.bankroll():.2f}€")

    def _on_bet_failed(self, payload):
        tx_id = payload.get("tx_id")
        if tx_id: self.money_manager.refund(tx_id)
        
        with self._lock:
            self.fail_count += 1
            if self.fail_count >= 3:
                self.circuit_open = True
                self.log_message.emit("⛔ SISTEMA IN PAUSA DI SICUREZZA.")
            self._save_state()

    def _save_state(self):
        try:
            with open(STATE_FILE, "w") as f:
                json.dump({"fail_count": self.fail_count, "circuit_open": self.circuit_open}, f)
        except: pass

    def _load_state(self):
        try:
            if os.path.exists(STATE_FILE):
                with open(STATE_FILE) as f:
                    data = json.load(f)
                    self.fail_count = data.get("fail_count", 0)
                    self.circuit_open = data.get("circuit_open", False)
        except: pass

    def _browser_watchdog(self):
        while True:
            time.sleep(15)
            if not self.worker.running: continue
            try: self.worker.submit(self._safe_browser_check)
            except: pass

    def _safe_browser_check(self):
        ex = self.worker.executor
        if ex and getattr(ex, "page", None):
            try:
                if ex.page.is_closed(): ex.recycle_browser()
            except: ex.recycle_browser()