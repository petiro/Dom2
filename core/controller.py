import logging
import threading
import time
import os
import yaml
import re
import requests
import psutil
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
            except Exception: continue

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

    def handle_signal(self, data: Dict[str, Any]) -> None:
        if not self.worker.running or self.circuit_open: return

        # 🔴 Rate Limit Segnali Globali (Anti-Spam)
        if time.time() - self.last_signal_ts < 2:
            self.logger.warning("Spam segnali (Rate Limit < 2s). Ignorato.")
            return
        self.last_signal_ts = time.time()

        with self._lock:
            if self.bet_lock:
                self.logger.warning("⚠️ Bet logica già in corso.")
                return
            self.bet_lock = True
            self.last_bet_ts = time.time() 

        try:
            raw_text = data.get("raw_text", "")
            chat_id = data.get("chat_id", "")
            active_robot = None

            if os.path.exists(ROBOTS_FILE):
                with open(ROBOTS_FILE, "r", encoding="utf-8") as f: robots = yaml.safe_load(f) or []
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
        self.consecutive_crashes = 0
        with self._lock:
            self.bet_lock = False
            self.circuit_open = False
        self.log_message.emit("💰 BET INVIATA AL BOOKMAKER.")

    def _on_bet_failed(self, payload):
        self.consecutive_crashes += 1
        if self.consecutive_crashes >= 3:
            self.logger.critical("🚨 CIRCUIT BREAKER: 3 Crash Consecutivi. Stop operazioni.")
            self.circuit_open = True

        with self._lock: self.bet_lock = False
        self.log_message.emit(f"❌ BET FALLITA: {payload.get('reason', 'errore')}")

    def _settled_watchdog(self):
        while True:
            time.sleep(60)
            if not self.worker.running: continue

            # ===============================
            # 🔴 OS-LEVEL ZOMBIE KILLER
            # ===============================
            if time.time() - self.last_worker_heartbeat > 300:
                self.logger.critical("💀 FREEZE TOTALE: Worker bloccato da >5 min (Chromium Zombie). Eseguo Hard Kill OS-level.")
                try:
                    for proc in psutil.process_iter(['pid', 'name']):
                        name = proc.info.get('name', '').lower()
                        if 'chrome' in name or 'chromium' in name:
                            proc.kill() 
                except Exception as exc:
                    self.logger.debug(f"Hard kill fallback: {exc}")
                
                self.last_worker_heartbeat = time.time()
                self.bet_lock = False
                
                try:
                    self.worker.submit(self.worker.executor.recycle_browser)
                except Exception: pass
                continue

            try:
                self.worker.submit(self._worker_maintenance_task)
            except Exception: pass

    def _worker_maintenance_task(self):
        # ☢️ NUCLEAR FREEZE MONITOR
        if self.bet_lock:
            freeze_time = time.time() - self.last_bet_ts
            if freeze_time > self.nuclear_threshold:
                self.logger.critical(f"☢️ Freeze > {self.nuclear_threshold}s → Nuclear Restart")
                self._nuclear_restart()
                return

        if self.worker.executor.login_fails >= 3:
            self.logger.critical("🚨 CIRCUIT BREAKER: 3 Login Falliti.")
            self.circuit_open = True
            return

        # ===============================
        # 🔴 CHROMIUM FREEZE WATCHDOG INVISIBILE
        # ===============================
        try:
            if self.worker.executor.page:
                start = time.time()
                self.worker.executor.page.evaluate("() => 1")
                latency = time.time() - start

                if latency > 5:
                    self.logger.critical(f"💀 Chromium freeze rilevato ({latency:.2f}s) → recycle invisibile")
                    self.worker.executor.recycle_browser()
                    return

                state = self.worker.executor.page.evaluate("() => document.readyState")
                if state not in ["complete", "interactive"]:
                    raise Exception("DOM frozen")
        except Exception:
            self.logger.critical("💀 Chromium non risponde → HARD RECYCLE invisibile")
            self.worker.executor.recycle_browser()
            return

        # Recycle Predittivo
        if hasattr(self.worker.executor, 'start_time') and self.worker.executor.start_time:
            uptime = time.time() - self.worker.executor.start_time
            if uptime > 14400 or self.worker.executor.bet_count >= 20: 
                self.logger.info("🔄 Recycle Predittivo (Uptime > 4h o Bets >= 20).")
                self.worker.executor.recycle_browser()
                return

        # Saldo Master Sync (Ogni 10 min)
        try:
            if not self.bet_lock and not self.db.pending():
                if time.time() - self.last_desync_check > 600:
                    self.last_desync_check = time.time()
                    
                    book_bal = self.worker.executor.get_balance()
                    db_bal = self.money_manager.bankroll()
                    
                    if book_bal is not None and db_bal is not None:
                        drift = abs(book_bal - db_bal)
                        if drift > 2.0: 
                            self.logger.critical(f"🚨 FINANCIAL DESYNC: Bet365 ({book_bal}€) vs Database ({db_bal}€). Drift di {drift}€. HARD STOP.")
                            self.circuit_open = True
                        else:
                            self.logger.info(f"✅ Sync Saldo OK. Bookmaker: {book_bal}€ | DB: {db_bal}€")
        except Exception as exc:
            self.logger.debug(f"Non-critical exception sync saldo: {exc}")

        if not self.bet_lock:
            self._check_settled()
            
        # 🔴 Aggiornamento heartbeat se tutto è andato a buon fine
        self.last_worker_heartbeat = time.time()

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