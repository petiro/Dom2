import logging
import threading
import time
import yaml
import os
import json
import re
from PySide6.QtCore import QObject, Signal

from core.event_bus import bus
from core.playwright_worker import PlaywrightWorker
from core.execution_engine import ExecutionEngine
from core.money_management import MoneyManager
from core.dom_executor_playwright import DomExecutorPlaywright
from core.database import Database
from core.config_paths import CONFIG_DIR
from core.config_loader import ConfigLoader

ROBOTS_FILE = os.path.join(CONFIG_DIR, "robots.yaml")

class SuperAgentController(QObject):
    log_message = Signal(str)

    def __init__(self, logger):
        super().__init__()
        self.logger = logger
        self.config_loader = ConfigLoader()
        self.config = self.config_loader.load_config()
        
        allow_bets = self.config.get("betting", {}).get("allow_place", False)
        
        self.db = Database()
        self.money_manager = MoneyManager()
        self.worker = PlaywrightWorker(logger)
        
        self.worker.executor = DomExecutorPlaywright(logger=logger, allow_place=allow_bets)
        self.engine = ExecutionEngine(bus, self.worker.executor, logger)
        
        # Lock Logico
        self.bet_in_progress = False
        self.circuit_open = False
        self._lock = threading.Lock()
        
        bus.subscribe("BET_SUCCESS", self._on_bet_success)
        bus.subscribe("BET_FAILED", self._on_bet_failed)
        self.worker.start()
        bus.start()
        
        # Loop Watchdog Esiti
        threading.Thread(target=self._settled_bets_watchdog, daemon=True).start()

    def fallback_parse(self, msg):
        m = re.search(r'(\d+)\s*-\s*(\d+)', msg)
        if m:
            return {"score": f"{m.group(1)}-{m.group(2)}", "market": "Winner"}
        return None

    def handle_signal(self, data):
        if not self.worker.running or self.circuit_open: return

        # BLOCCO RACE CONDITION: Se in corso, scarta.
        with self._lock:
            if self.bet_in_progress:
                self.logger.warning("⚠️ Bet in corso. Ignoro nuovo segnale.")
                return
            self.bet_in_progress = True

        try:
            if not data.get("teams") or not data.get("market"):
                fallback_data = self.fallback_parse(data.get("raw_text", ""))
                if fallback_data: data.update(fallback_data)
                
            self.worker.submit(self.engine.process_signal, data, self.money_manager)
        except Exception as e:
            # Rilascio manuale se fallisce l'inserimento
            with self._lock: self.bet_in_progress = False
            self.logger.error(f"Errore handle_signal: {e}")

    def _on_bet_success(self, payload):
        with self._lock:
            self.bet_in_progress = False
            self.circuit_open = False
        
        tx_id = payload.get("tx_id")
        # Inizialmente registra a 0. Il watchdog aggiornerà il payout reale.
        if tx_id: self.money_manager.win(tx_id, payout=0)
        self.log_message.emit("💰 BET PIAZZATA CORRETTAMENTE!")

    def _on_bet_failed(self, payload):
        with self._lock:
            self.bet_in_progress = False
        self.log_message.emit(f"❌ BET FALLITA/SCARTATA: {payload.get('reason', 'Errore')}")

    def _settled_bets_watchdog(self):
        while True:
            time.sleep(60)
            if not self.worker.running or self.bet_in_progress: continue
            try:
                self.worker.submit(self._check_and_update_roserpina)
            except: pass

    def _check_and_update_roserpina(self):
        result_data = self.worker.executor.check_settled_bets()
        if not result_data: return

        status = result_data.get("status")
        payout = result_data.get("payout", 0.0)

        pending = self.db.pending()
        if not pending: return
        
        last_tx = pending[-1]['tx_id']

        # 🔴 FIX 4: PAYOUT REALE E AGGIORNAMENTO ROBUST
        if status == "WIN":
            self.logger.info(f"🏆 ESITO REALE: WIN. Payout: {payout}€. Sincronizzo Roserpina.")
            self.money_manager.win(last_tx, payout=payout)
        elif status == "LOSS":
            self.logger.info("❌ ESITO REALE: LOSS. Aggiorno Roserpina.")
            # self.money_manager.loss(last_tx) # Decommenta se nel tuo MM la loss aggiorna la progressione
        elif status == "VOID":
            self.logger.info("🔄 ESITO REALE: VOID. Rollback.")
            self.money_manager.refund(last_tx)