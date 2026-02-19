import logging
import threading
import time
import os
import yaml
import re
import requests
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
    ai_analysis_ready = Signal(str)

    def __init__(self, logger):
        super().__init__()
        self.logger = logger
        self.config_loader = ConfigLoader()
        self.config = self.config_loader.load_config()

        allow_bets = self.config.get("betting", {}).get("allow_place", False)

        self.db = Database()
        self.money_manager = MoneyManager()
        self.worker = PlaywrightWorker(logger)

        self.worker.executor = DomExecutorPlaywright(
            logger=logger,
            allow_place=allow_bets
        )

        self.engine = ExecutionEngine(bus, self.worker.executor, logger)

        self.bet_lock = False
        self.circuit_open = False
        self._lock = threading.Lock()
        self.last_desync_check = 0 

        bus.subscribe("BET_SUCCESS", self._on_bet_success)
        bus.subscribe("BET_FAILED", self._on_bet_failed)

        self.worker.start()
        bus.start()
        threading.Thread(target=self._settled_watchdog, daemon=True).start()

    def test_ai_strategy(self, description, msg_template):
        threading.Thread(target=self._run_ai_analysis, args=(description, msg_template)).start()

    def _run_ai_analysis(self, description, msg_template):
        api_key = self.config.get("openrouter", {}).get("api_key")
        if not api_key: return
        prompt = f"Regola: '{description}'. Messaggio: '{msg_template}'. Spiega: OBIETTIVO, DATI, LOGICA, MERCATO."
        MODELS = ["arcee-ai/trinity-large-preview:free", "google/gemini-2.0-flash-lite-preview-02-05:free"]
        
        for model in MODELS:
            try:
                resp = requests.post("https://openrouter.ai/api/v1/chat/completions", headers={"Authorization": f"Bearer {api_key}", "HTTP-Referer": "https://github.com"}, json={"model": model, "messages": [{"role": "user", "content": prompt}]}, timeout=12)
                if resp.status_code == 200:
                    self.ai_analysis_ready.emit(f"✅ (Modello: {model})\n\n" + resp.json()['choices'][0]['message']['content'])
                    return
            except: continue

    def fallback_parse(self, msg):
        m = re.search(r'(\d+)\s*-\s*(\d+)', msg)
        if m: return {"score": f"{m.group(1)}-{m.group(2)}", "market": "Winner"}
        return None

    def _smart_parse(self, text, template):
        extracted = {}
        match_teams = re.search(r"🆚\s*(.*?)\s*v\s*(.*)|🆚\s*(.*?)\s*vs\s*(.*)", text)
        if match_teams: extracted["teams"] = f"{match_teams.group(1) or match_teams.group(3)} - {match_teams.group(2) or match_teams.group(4)}"
        if "OVER" in text.upper(): extracted["market"] = "OVER"
        return extracted

    def handle_signal(self, data):
        if not self.worker.running or self.circuit_open: return

        pending_tx = self.db.pending()
        if pending_tx:
            last = pending_tx[-1]
            tx_time = last.get("timestamp", 0) 
            if time.time() - tx_time > 7200:
                self.logger.warning(f"⚠️ Pending TX bloccata da >2h. Eseguo Refund Sicurezza.")
                self.money_manager.refund(last["tx_id"])
            else:
                self.logger.warning(f"🚨 TRANSAZIONE PENDENTE NEL DB! Blocco segnali.")
                return

        with self._lock:
            if self.bet_lock:
                self.logger.warning("⚠️ Bet logica già in corso.")
                return
            self.bet_lock = True

        try:
            raw_text = data.get("raw_text", "")
            chat_id = data.get("chat_id", "")
            active_robot = None

            if os.path.exists(ROBOTS_FILE):
                with open(ROBOTS_FILE, "r") as f: robots = yaml.safe_load(f) or []
                for robot in robots:
                    if not robot.get("enabled", True): continue
                    
                    req_chats_raw = robot.get("specific_chat_id", "")
                    if req_chats_raw:
                        allowed_chats = [c.strip() for c in str(req_chats_raw).split(',') if c.strip()]
                        if allowed_chats and str(chat_id) not in allowed_chats: continue

                    triggers = robot.get("trigger_words", [])
                    if not triggers or any(good.lower() in raw_text.lower() for good in triggers):
                        active_robot = robot
                        self.log_message.emit(f"🤖 ROBOT: {robot['name']}")
                        break

            if active_robot:
                tmpl = active_robot.get("msg_template", "")
                if tmpl: data.update(self._smart_parse(raw_text, tmpl))

            if not data.get("teams"): data.update(self.fallback_parse(raw_text) or {"teams": "Match Fallback", "market": "Winner"})
                
            self.worker.submit(self.engine.process_signal, data, self.money_manager)

        except Exception as e:
            self.logger.error(f"Errore handle_signal: {e}")
            with self._lock: self.bet_lock = False

    def _on_bet_success(self, payload):
        with self._lock:
            self.bet_lock = False
            self.circuit_open = False
        self.log_message.emit("💰 BET INVIATA AL BOOKMAKER.")

    def _on_bet_failed(self, payload):
        with self._lock: self.bet_lock = False
        self.log_message.emit(f"❌ BET FALLITA: {payload.get('reason', 'errore')}")
        tx = payload.get("tx_id")
        if tx: self.money_manager.refund(tx)

    # ----------------------------------------------------------------------
    # 🔴 FIX 2: IL WATCHDOG NON TOCCA PIÙ IL BROWSER DIRETTAMENTE
    # Manda un unico mega-task di "Manutenzione" al worker, rendendolo 100% thread-safe.
    # ----------------------------------------------------------------------
    def _settled_watchdog(self):
        while True:
            time.sleep(60)
            if not self.worker.running: continue
            
            # Delega l'intero check al worker per evitare il crash del Greenlet
            try:
                self.worker.submit(self._worker_maintenance_task)
            except: pass

    def _worker_maintenance_task(self):
        # 1. Heartbeat
        try:
            if self.worker.executor.page:
                state = self.worker.executor.page.evaluate("() => document.readyState")
                if state not in ["complete", "interactive"]:
                    raise Exception("DOM not ready")
        except Exception:
            self.logger.warning("💀 Sessione Heartbeat morta (Playwright freeze) → Riavvio browser preventivo.")
            self.worker.executor.recycle_browser()
            return # Se lo riavvio, non controllo gli esiti

        # 2. Recycle 4h
        if hasattr(self.worker.executor, 'start_time') and self.worker.executor.start_time:
            if time.time() - self.worker.executor.start_time > 14400: # 4h
                self.logger.info("🔄 Browser aperto da 4 ore. Riciclo programmato...")
                self.worker.executor.recycle_browser()
                return

        # 3. Snapshot Desync
        try:
            if not self.bet_lock and not self.db.pending():
                if time.time() - self.last_desync_check > 300:
                    self.last_desync_check = time.time()
                    saldo_book = self.worker.executor.get_balance()
                    saldo_db = self.money_manager.bankroll()
                    if saldo_book is not None and saldo_db is not None:
                        if abs(saldo_book - saldo_db) > 1.0: 
                            self.logger.warning(f"⚠️ DESYNC SALDO: Bookmaker ({saldo_book}€) vs Database ({saldo_db}€)")
        except: pass

        # 4. Check Settled
        if not self.bet_lock:
            self._check_settled()

    def _check_settled(self):
        result = self.worker.executor.check_settled_bets()
        if not result: return

        status = result.get("status")
        payout = result.get("payout", 0)

        pending = self.db.pending()
        if not pending: return

        tx_id = pending[-1]["tx_id"]

        if status == "WIN":
            self.logger.info(f"🏆 WIN reale ({payout}€). Aggiorno DB.")
            self.money_manager.win(tx_id, payout)
        elif status == "LOSS":
            self.logger.info("❌ LOSS reale. Aggiorno DB.")
            self.money_manager.loss(tx_id)
        elif status == "VOID":
            self.logger.info("🔄 VOID reale. Rollback DB.")
            self.money_manager.refund(tx_id)
