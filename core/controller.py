import logging
import threading
import time
import os
import json
import re
import requests
import psutil
from pathlib import Path
from typing import Dict, Any
from PySide6.QtCore import QObject, Signal

from core.event_bus import bus
from core.playwright_worker import PlaywrightWorker
from core.telegram_worker import TelegramWorker  # 🔴 FIX 1: Import Telegram
from core.execution_engine import ExecutionEngine
from core.money_management import MoneyManager
from core.dom_executor_playwright import DomExecutorPlaywright
from core.database import Database
from core.config_paths import CONFIG_DIR
from core.config_loader import ConfigLoader
from core.secure_storage import RobotManager

class SuperAgentController(QObject):
    log_message = Signal(str)
    ai_analysis_ready = Signal(str)

    def __init__(self, logger):
        super().__init__()
        self.logger = logger
        self.config_loader = ConfigLoader()
        self.config = self.config_loader.load_config()

        allow_bets = self.config.get("betting", {}).get("allow_place", False)

        self.db = Database()
        self.money_manager = MoneyManager(self.db)
        
        self.worker = PlaywrightWorker(logger)
        self.worker.executor = DomExecutorPlaywright(logger=logger, allow_place=allow_bets)
        self.engine = ExecutionEngine(bus, self.worker.executor, logger)

        # 🔴 FIX 1: Telegram Worker riattivato e collegato!
        self.telegram = TelegramWorker(self.config)
        self.telegram.message_received.connect(self.process_signal)

        self.bet_lock = False
        self.circuit_open = False
        self._lock = threading.Lock()
        
        self.last_bet_ts = 0 
        self.last_signal_ts = 0
        self.consecutive_crashes = 0
        self.last_desync_check = time.time()
        
        self.last_worker_heartbeat = time.time()
        self.nuclear_threshold = 90  

        bus.subscribe("BET_SUCCESS", self._on_bet_success)
        bus.subscribe("BET_FAILED", self._on_bet_failed)

        self.worker.start()
        self.telegram.start()  # 🔴 FIX 1: Avvia l'ascolto!
        bus.start()
        threading.Thread(target=self._settled_watchdog, daemon=True).start()

    def _load_robots(self):
        return RobotManager().all()

    def _nuclear_restart(self):
        self.logger.critical("☢️ NUCLEAR RESTART ATTIVATO")
        try:
            try: self.worker.stop()
            except Exception: pass
            
            try: self.telegram.stop()
            except Exception: pass

            try: self.worker.executor.close()
            except Exception: pass

            self.bet_lock = False
            self.circuit_open = False
            self.consecutive_crashes = 0

            allow_bets = self.config.get("betting", {}).get("allow_place", False)
            self.worker.executor = DomExecutorPlaywright(logger=self.logger, allow_place=allow_bets)
            self.worker.start()
            self.telegram = TelegramWorker(self.config)
            self.telegram.message_received.connect(self.process_signal)
            self.telegram.start()
            
            self.last_worker_heartbeat = time.time()
            self.logger.critical("☢️ NUCLEAR RESTART COMPLETATO. Sistema di nuovo online.")
        except Exception as e:
            self.logger.critical(f"NUCLEAR FAILURE: {e}")

    def test_ai_strategy(self, description, msg_template):
        threading.Thread(target=self._run_ai_analysis, args=(description, msg_template)).start()

    def _run_ai_analysis(self, description, msg_template):
        api_key = ""
        key_file = os.path.join(str(Path.home()), ".superagent_data", "openrouter_key.dat")
        if os.path.exists(key_file):
            with open(key_file, "r", encoding="utf-8") as f:
                api_key = f.read().strip()
                
        if not api_key:
            self.ai_analysis_ready.emit("❌ ERRORE: API Key OpenRouter mancante. Inseriscila nella UI.")
            return
            
        prompt = f"Regola: '{description}'. Messaggio: '{msg_template}'. Spiega: OBIETTIVO, DATI, LOGICA, MERCATO."
        MODELS = ["arcee-ai/trinity-large-preview:free", "google/gemini-2.0-flash-lite-preview-02-05:free"]
        
        for model in MODELS:
            try:
                resp = requests.post("https://openrouter.ai/api/v1/chat/completions", headers={"Authorization": f"Bearer {api_key}", "HTTP-Referer": "https://github.com"}, json={"model": model, "messages": [{"role": "user", "content": prompt}]}, timeout=12)
                if resp.status_code == 200:
                    self.ai_analysis_ready.emit(f"✅ (Modello: {model})\n\n" + resp.json()['choices'][0]['message']['content'])
                    return
            except Exception: continue
        self.ai_analysis_ready.emit("❌ ERRORE: Analisi AI fallita o server OpenRouter non disponibile.")

    def process_signal(self, payload):
        self.logger.info(f"📥 Controller instrada segnale: {payload}")
        if isinstance(payload, str):
            payload = {"teams": "Analisi Auto", "market": "N/A", "raw_text": payload}
            
        if not self.worker.running:
            self.logger.error("❌ Worker spento. Segnale droppato.")
            return False
            
        self.worker.submit(self.engine.process_signal, payload, self.money_manager)
        return True

    def handle_signal(self, signal):
        self.logger.info("🛠️ [COMPATIBILITY] Ricevuto segnale dal Tester, inoltro al motore V8...")
        return self.process_signal(signal)

    def _on_bet_success(self, event):
        self.logger.info(f"✅ Bet Success Event: {event}")

    def _on_bet_failed(self, event):
        self.logger.info(f"❌ Bet Failed Event: {event}")

    # 🔴 FIX 2: WATCHDOG IMPLEMENTATO (Sblocca i loop di pending eterni)
    def _settled_watchdog(self):
        self.logger.info("👁️ Watchdog Refertazione DB avviato in background.")
        while True:
            time.sleep(120)  # Controlla referti ogni 2 minuti
            try:
                pending_bets = self.money_manager.db.pending()
                if not pending_bets:
                    continue
                
                # Accodiamo al PlaywrightWorker il controllo del Bookmaker
                def check_job():
                    try:
                        self.logger.info(f"⏳ Controllo {len(pending_bets)} referti pendenti su Bookmaker...")
                        res = self.worker.executor.check_settled_bets()
                        if res and res.get("status"):
                            status = res["status"]
                            payout = res.get("payout", 0.0)
                            
                            # Refertiamo la più vecchia pending in coda
                            oldest_tx = pending_bets[0]["tx_id"]
                            if status == "WIN":
                                self.money_manager.win(oldest_tx, payout)
                            elif status == "LOSS":
                                self.money_manager.loss(oldest_tx)
                            elif status == "VOID":
                                self.money_manager.refund(oldest_tx)
                                
                            self.logger.info(f"⚖️ Esito refertato in DB! TX: {oldest_tx[:8]} -> {status} (€{payout})")
                    except Exception as e:
                        self.logger.error(f"Errore lettura referti bookmaker: {e}")
                
                self.worker.submit(check_job)
                
            except Exception as e:
                self.logger.error(f"Errore Loop Watchdog PENDING: {e}")
