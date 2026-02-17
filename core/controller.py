import threading
import logging
import time
from PySide6.QtCore import QObject, Signal

from core.event_bus import bus
from core.playwright_worker import PlaywrightWorker
from core.execution_engine import ExecutionEngine
from core.money_management import MoneyManager
from core.dom_executor_playwright import DomExecutorPlaywright
from core.database import Database

class SuperAgentController(QObject):
    log_message = Signal(str)

    def __init__(self, logger):
        super().__init__()
        self.logger = logger
        
        # Inizializza DB e Manager Transazionale
        self.db = Database()
        self.money_manager = MoneyManager()

        self.worker = PlaywrightWorker(logger)
        self.worker.executor = DomExecutorPlaywright(logger=logger)
        self.engine = ExecutionEngine(bus, self.worker.executor)

        self.fail_count = 0
        self.circuit_open = False
        self._lock = threading.Lock()
        
        bus.subscribe("BET_SUCCESS", self._on_bet_success)
        bus.subscribe("BET_FAILED", self._on_bet_failed)
        
        self.worker.start()
        bus.start()
        
        # Avvia Recovery per transazioni interrotte
        self._perform_recovery()

        threading.Thread(target=self._browser_watchdog, daemon=True).start()

    def _perform_recovery(self):
        """Resilienza 10/10: Controlla se il bot è crashato durante una bet."""
        pending = self.db.get_pending_transactions()
        if pending:
            self.log_message.emit(f"🔄 RECOVERY: Trovate {len(pending)} transazioni appese.")
            self.logger.warning(f"Recovery started for {len(pending)} transactions.")
            
            for row in pending:
                tx_id = row['tx_id']
                # Strategia conservativa: Rimborsare se non siamo sicuri
                # In V9 si potrebbe controllare la cronologia del sito
                self.money_manager.refund(tx_id)
                self.log_message.emit(f"↩️ Transazione {tx_id[:8]} annullata e rimborsata per sicurezza.")

    def handle_signal(self, data):
        if self.circuit_open:
            self.logger.warning("Circuit open. Ignored.")
            return

        # Passa anche il riferimento al money manager per la gestione TX
        self.worker.submit(self.engine.process_signal, data, self.money_manager)

    def _on_bet_success(self, payload):
        # Il payload deve contenere il tx_id generato nell'engine
        tx_id = payload.get("tx_id")
        payout = float(payload.get("payout", 0)) # Stake * Odds
        
        if tx_id:
            self.money_manager.confirm_win(tx_id, payout)
        
        self.fail_count = 0
        bal = self.money_manager.get_bankroll()
        self.log_message.emit(f"💰 WIN | Saldo: {bal:.2f}€")

    def _on_bet_failed(self, payload):
        tx_id = payload.get("tx_id")
        reason = payload.get("reason", "Unknown")
        
        # Se è un errore tecnico (es. selettore non trovato), rimborsa.
        # Se è una perdita confermata (es. bet persa), conferma loss.
        # Qui assumiamo rimborso per safety in caso di crash pipeline
        if tx_id:
            if "loss" in reason.lower():
                self.money_manager.confirm_loss(tx_id)
            else:
                self.money_manager.refund(tx_id)
                
        self.fail_count += 1
        self.log_message.emit(f"FAIL #{self.fail_count}: {reason}")

        if self.fail_count >= 3:
            self.logger.critical("🚨 CIRCUIT BREAKER TRIGGERED")
            self.circuit_open = True
            self.worker.stop()

    def _browser_watchdog(self):
        while True:
            time.sleep(10)
            ex = self.worker.executor
            if ex and getattr(ex, "page", None):
                try:
                    if ex.page.is_closed():
                        self.logger.warning("Watchdog restart browser")
                        ex.recycle_browser()
                except: pass