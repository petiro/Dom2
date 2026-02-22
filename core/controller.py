import logging
import threading
import time
import os
import requests
from pathlib import Path
from typing import Dict, Any
from PySide6.QtCore import QObject, Signal

from core.event_bus import bus
from core.playwright_worker import PlaywrightWorker
from core.telegram_worker import TelegramWorker
from core.execution_engine import ExecutionEngine
from core.money_management import MoneyManager
from core.dom_executor_playwright import DomExecutorPlaywright
from core.database import Database
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

        # Inizializza Telegram Worker ma non farlo partire
        self.telegram = TelegramWorker(self.config)
        self.telegram.message_received.connect(self.process_signal)

        # Stati del Command Center
        self.is_running = False 
        self.engine.betting_enabled = False
        self._bus_started = False

        self.bet_lock = False
        self.circuit_open = False
        self._lock = threading.Lock()
        
        self.last_worker_heartbeat = time.time()

        bus.subscribe("BET_SUCCESS", self._on_bet_success)
        bus.subscribe("BET_FAILED", self._on_bet_failed)

        threading.Thread(target=self._settled_watchdog, daemon=True).start()

    # =========================================================
    # CONTROLLI MOTORE (START / STOP HEDGE-GRADE)
    # =========================================================
    def start_listening(self):
        """Sveglia il worker di Telegram, Playwright e l'EventBus in sicurezza"""
        if getattr(self, "is_running", False):
            self.logger.warning("Motore già attivo. Ignoro doppio comando.")
            return

        self.logger.info("🟢 MOTORE AVVIATO: Inizializzazione servizi...")
        self.is_running = True
        
        # Sblocco globale delle scommesse (Circuit Breaker)
        if hasattr(self, "engine"):
            self.engine.betting_enabled = True

        if not getattr(self, "_bus_started", False):
            bus.start()
            self._bus_started = True

        if not getattr(self.worker, "running", False):
            self.worker.start()

        if hasattr(self, "telegram") and self.telegram:
            if not getattr(self.telegram, "running", False):
                self.telegram.start()
            
    def stop_listening(self):
        """Graceful shutdown: ferma Telegram, blocca nuovi segnali, finisce bet in corso"""
        if not getattr(self, "is_running", False):
            return

        self.logger.warning("🔴 STOP MOTORE (Graceful Shutdown)...")
        self.is_running = False

        # Blocco betting immediato (Circuit Breaker)
        if hasattr(self, "engine"):
            self.engine.betting_enabled = False

        if hasattr(self, "telegram") and self.telegram:
            self.telegram.stop()
            self.logger.info("Worker disconnesso. Nessun nuovo segnale verrà processato.")

    def _load_robots(self):
        return RobotManager().all()

    def _match_robot(self, payload, robot_config):
        text = payload.get("raw_text", "").lower()
        if not text:
            text = f"{payload.get('teams', '')} {payload.get('market', '')}".lower()
            
        triggers = robot_config.get("trigger_words", [])
        if isinstance(triggers, str):
            triggers = [t.strip() for t in triggers.split(",") if t.strip()]
            
        excludes = robot_config.get("exclude_words", [])
        if isinstance(excludes, str):
            excludes = [e.strip() for e in excludes.split(",") if e.strip()]
            
        for ex in excludes:
            if ex and str(ex).lower() in text:
                return False
                
        if not triggers:
            return True 
            
        for t in triggers:
            if str(t).lower() in text:
                return True
                
        return False

    def process_signal(self, payload):
        if not getattr(self, "is_running", False):
            self.logger.warning("⛔ Motore OFF → segnale Telegram ignorato.")
            return False

        self.logger.info(f"📥 Controller instrada segnale: {payload}")
        if isinstance(payload, str):
            payload = {"teams": "Analisi Auto", "market": "N/A", "raw_text": payload}
            
        if not self.worker.running:
            self.logger.error("❌ Worker Playwright spento. Segnale droppato.")
            return False
            
        robots = self._load_robots()
        if not robots:
            self.logger.warning("Nessun robot configurato nel Vault. Segnale droppato.")
            return False
            
        matched = False
        for r in robots:
            # Filtro START/STOP singolo robot
            if not r.get("is_active", True):
                continue
                
            if self._match_robot(payload, r):
                self.logger.info(f"🤖 Match Robot Triggered: {r.get('name')}")
                
                payload["is_active"] = True
                payload["robot_name"] = r.get("name")
                
                self.worker.submit(self.engine.process_signal, payload, self.money_manager)
                matched = True
                return True

        if not matched:
            self.logger.info("Nessun robot ha trovato match di parole chiave → Skip segnale.")
            return False

    def handle_signal(self, signal):
        self.logger.info("🛠️ [COMPATIBILITY] Ricevuto segnale, inoltro...")
        return self.process_signal(signal)

    def _on_bet_success(self, event):
        self.logger.info(f"✅ Bet Success Event: {event}")

    def _on_bet_failed(self, event):
        self.logger.info(f"❌ Bet Failed Event: {event}")

    def _settled_watchdog(self):
        self.logger.info("👁️ Watchdog Refertazione DB avviato in background.")
        while True:
            time.sleep(120)
            try:
                pending_bets = self.money_manager.db.pending()
                if not pending_bets:
                    continue
                
                def check_job():
                    try:
                        self.logger.info(f"⏳ Controllo {len(pending_bets)} referti pendenti su Bookmaker...")
                        res = self.worker.executor.check_settled_bets()
                        if res and res.get("status"):
                            status = res["status"]
                            payout = res.get("payout", 0.0)
                            
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
                
                if getattr(self, "is_running", False) and getattr(self.worker, "running", False):
                    self.worker.submit(check_job)
                
            except Exception as e:
                self.logger.error(f"Errore Loop Watchdog PENDING: {e}")