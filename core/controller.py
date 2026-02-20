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
from core.execution_engine import ExecutionEngine
from core.money_management import MoneyManager
from core.dom_executor_playwright import DomExecutorPlaywright
from core.database import Database
from core.config_paths import CONFIG_DIR
from core.config_loader import ConfigLoader

# 🔴 FIX DEFINITIVO: Legge i robot dal Vault sicuro
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

        self.bet_lock = False
        self.circuit_open = False
        self._lock = threading.Lock()
        
        self.last_bet_ts = 0 
        self.last_signal_ts = 0
        self.consecutive_crashes = 0
        self.last_desync_check = time.time()
        
        # ☢️ Init variabili di sicurezza estreme
        self.last_worker_heartbeat = time.time()
        self.nuclear_threshold = 90  # Secondi massimi di blocco prima del reset totale

        bus.subscribe("BET_SUCCESS", self._on_bet_success)
        bus.subscribe("BET_FAILED", self._on_bet_failed)

        self.worker.start()
        bus.start()
        threading.Thread(target=self._settled_watchdog, daemon=True).start()

    def _load_robots(self):
        # 🔴 FIX: Usa il nuovo Manager Vault invece del vecchio robots.yaml
        return RobotManager().all()

    def _nuclear_restart(self):
        self.logger.critical("☢️ NUCLEAR RESTART ATTIVATO")
        try:
            # 1. Stop forzato worker
            try:
                self.worker.stop()
            except Exception:
                pass

            # 2. Stop forzato executor
            try:
                self.worker.executor.close()
            except Exception:
                pass

            # 3. Reset stato interno
            self.bet_lock = False
            self.circuit_open = False
            self.consecutive_crashes = 0

            # 4. Ricrea executor pulito
            allow_bets = self.config.get("betting", {}).get("allow_place", False)
            self.worker.executor = DomExecutorPlaywright(
                logger=self.logger,
                allow_place=allow_bets
            )

            # 5. Riavvia worker
            self.worker.start()
            self.last_worker_heartbeat = time.time()

            self.logger.critical("☢️ NUCLEAR RESTART COMPLETATO. Sistema di nuovo online.")
        except Exception as e:
            self.logger.critical(f"NUCLEAR FAILURE: {e}")

    def test_ai_strategy(self, description, msg_template):
        threading.Thread(target=self._run_ai_analysis, args=(description, msg_template)).start()

    def _run_ai_analysis(self, description, msg_template):
        # 🔴 LETTURA SICURA API KEY OPENROUTER DAL VAULT
        api_key = ""
        key_file = os.path.join(str(Path.home()), ".superagent_data", "openrouter_key.dat")
        if os.path.exists(key_file):
            with open(key_file, "r", encoding="utf-8") as f:
                api_key = f.read().strip()
                
        if not api_key:
            self.ai_analysis_ready.emit("❌ ERRORE: API Key OpenRouter mancante. Inseriscila nella UI (Tab Cloud & API).")
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

    # ==========================================
    # 🔴 COMPATIBILITY LAYER FOR HEDGE TEST CI
    # ==========================================
    def handle_signal(self, signal):
        """
        Wrapper compatibile con hedge_super_tester.py.
        Inoltra il finto segnale alla vera logica V8.
        """
        try:
            self.logger.info("🛠️ [COMPATIBILITY] Ricevuto segnale dal Tester, inoltro al motore V8...")
            
            # Se la tua architettura V8 processa il segnale in un metodo specifico (es: process_signal)
            if hasattr(self, "process_signal"):
                return self.process_signal(signal)
            
            # Altrimenti spara nell'EventBus globale per far svegliare il Worker    
            from core.event_bus import bus
            bus.emit("NEW_SIGNAL", signal)
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Errore nel compatibility layer handle_signal: {e}", exc_info=True)
            return False

    def _on_bet_success(self, event):
        pass

    def _on_bet_failed(self, event):
        pass

    def _settled_watchdog(self):
        pass
