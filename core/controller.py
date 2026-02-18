import logging
import threading
import time
import yaml
import os
from PySide6.QtCore import QObject, Signal

from core.event_bus import bus
from core.playwright_worker import PlaywrightWorker
from core.execution_engine import ExecutionEngine
from core.money_management import MoneyManager
from core.dom_executor_playwright import DomExecutorPlaywright
from core.database import Database
from core.auto_mapper_worker import AutoMapperWorker
from core.dom_self_healing import DOMSelfHealing
from core.config_paths import CONFIG_DIR

class SuperAgentController(QObject):
    log_message = Signal(str)

    def __init__(self, logger):
        super().__init__()
        self.logger = logger

        # 1. Core Data
        self.db = Database()
        self.money = MoneyManager()

        # 2. Core Execution
        self.worker = PlaywrightWorker(logger)
        self.worker.executor = DomExecutorPlaywright(logger=logger)
        self.engine = ExecutionEngine(bus, self.worker.executor)
        
        # 3. Intelligence
        self.self_healer = DOMSelfHealing(self.worker.executor)

        # 4. State
        self.fail_count = 0
        self.circuit = False
        self._lock = threading.Lock()

        # 5. Startup
        bus.subscribe("BET_SUCCESS", self._win)
        bus.subscribe("BET_FAILED", self._fail)

        self.worker.start()
        bus.start()
        self._recovery()

        threading.Thread(target=self._watchdog, daemon=True).start()
        self.log_message.emit("✅ SISTEMA V8.4 SINGOLARITÀ ATTIVO")

    def _recovery(self):
        pending = self.db.pending()
        if pending:
            self.logger.warning(f"Recovery: {len(pending)} transazioni appese.")
            for p in pending:
                self.money.refund(p["tx_id"])

    def start_auto_mapping(self, url):
        self.log_message.emit(f"🧠 Avvio AI Auto-Mapping su {url}...")
        self.mapper = AutoMapperWorker(self.worker.executor, url)
        self.mapper.log.connect(self.log_message.emit)
        self.mapper.finished.connect(self._on_mapping_done)
        self.worker.submit(self.mapper.run)

    def _on_mapping_done(self, selectors):
        if not selectors:
            self.log_message.emit("❌ Mapping fallito o vuoto.")
            return
        
        self.log_message.emit(f"✅ Mapping OK: {len(selectors)} selettori salvati.")
        # Reload immediato executor se necessario
        # self.worker.executor.reload_selectors()

    def handle_signal(self, data):
        if self.circuit:
            self.logger.warning("Circuito aperto. Segnale ignorato.")
            return
        self.worker.submit(self.engine.process_signal, data, self.money)

    def _win(self, payload):
        with self._lock:
            self.fail_count = 0
            self.circuit = False
        
        tx = payload.get("tx_id")
        payout = payload.get("payout", 0)
        if tx: self.money.win(tx, payout)
        
        bal = self.money.bankroll()
        self.log_message.emit(f"💰 WIN | Nuovo Saldo: {bal:.2f}€")

    def _fail(self, payload):
        tx = payload.get("tx_id")
        if tx: self.money.refund(tx)
        
        with self._lock:
            self.fail_count += 1
            if self.fail_count >= 3:
                self.circuit = True
                self.log_message.emit("⛔ CIRCUIT BREAKER ATTIVATO")
                self.worker.stop()
        
        self.log_message.emit(f"❌ FAIL: {payload.get('reason','')}")

    def _watchdog(self):
        while True:
            time.sleep(10)
            ex = self.worker.executor
            if ex and getattr(ex, "page", None):
                try:
                    if ex.page.is_closed():
                        self.logger.warning("Watchdog: Browser crash. Restarting...")
                        ex.recycle_browser()
                except: pass
