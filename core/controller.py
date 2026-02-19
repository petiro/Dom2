import logging
import threading
import time
import yaml
import os
import json
import requests
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

STATE_FILE = os.path.join(CONFIG_DIR, "runtime_state.json")
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
        
        self.worker.executor = DomExecutorPlaywright(logger=logger, allow_place=allow_bets)
        self.engine = ExecutionEngine(bus, self.worker.executor)
        
        self.fail_count = 0
        self.circuit_open = False
        self._lock = threading.Lock()
        
        bus.subscribe("BET_SUCCESS", self._on_bet_success)
        bus.subscribe("BET_FAILED", self._on_bet_failed)
        self.worker.start()
        bus.start()
        
        msg = "REAL MONEY 💸" if allow_bets else "SIMULATION 🛡️"
        self.log_message.emit(f"✅ SISTEMA V8.5 AVVIATO - MODALITÀ: {msg}")

    def test_ai_strategy(self, description, msg_template):
        threading.Thread(target=self._run_ai_analysis, args=(description, msg_template)).start()

    def _run_ai_analysis(self, description, msg_template):
        api_key = self.config.get("openrouter", {}).get("api_key")
        if not api_key or "sk-" not in api_key:
            self.ai_analysis_ready.emit("❌ Errore: API Key OpenRouter mancante nel config.yaml")
            return

        prompt = f"""
        SEI UN BOT SCOMMESSE. 
        Regola: "{description}"
        Messaggio: "{msg_template}"
        Spiega: 🎯 OBIETTIVO, 🔍 DATI ESTRATTI, 🧠 LOGICA, 🛒 MERCATO. Rispondi in italiano.
        """
        try:
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
            payload = {"model": "google/gemini-2.0-flash-lite-preview-02-05:free", "messages": [{"role": "user", "content": prompt}]}
            resp = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload, timeout=15)
            if resp.status_code == 200:
                self.ai_analysis_ready.emit(resp.json()['choices'][0]['message']['content'])
            else:
                self.ai_analysis_ready.emit(f"❌ Errore API: {resp.status_code}")
        except Exception as e:
            self.ai_analysis_ready.emit(f"❌ Errore: {e}")

    def _smart_parse(self, text, template):
        extracted = {}
        match_teams = re.search(r"🆚\s*(.*?)\s*v\s*(.*)|🆚\s*(.*?)\s*vs\s*(.*)", text)
        if match_teams:
            t1 = match_teams.group(1) or match_teams.group(3)
            t2 = match_teams.group(2) or match_teams.group(4)
            extracted["teams"] = f"{t1.strip()} - {t2.strip()}"
            
        if "OVER" in text.upper(): extracted["market"] = "OVER"
        elif "UNDER" in text.upper(): extracted["market"] = "UNDER"
        return extracted

    def handle_signal(self, data):
        if not self.worker.running or self.circuit_open: return

        active_robot = None
        raw_text = data.get("raw_text", "")
        chat_id = data.get("chat_id", "")

        if os.path.exists(ROBOTS_FILE):
            try:
                with open(ROBOTS_FILE, "r") as f:
                    robots = yaml.safe_load(f) or []
                for robot in robots:
                    if not robot.get("enabled", True): continue
                    
                    req_chats_raw = robot.get("specific_chat_id", "")
                    if req_chats_raw:
                        allowed_chats = [c.strip() for c in str(req_chats_raw).split(',') if c.strip()]
                        if allowed_chats and str(chat_id) not in allowed_chats: continue

                    excludes = robot.get("exclude_words", [])
                    if excludes and any(bad.lower() in raw_text.lower() for bad in excludes): continue

                    triggers = robot.get("trigger_words", [])
                    if not triggers or any(good.lower() in raw_text.lower() for good in triggers):
                        active_robot = robot
                        self.log_message.emit(f"🤖 ROBOT ATTIVATO: {robot['name']}")
                        break
            except Exception as e: self.logger.error(f"Errore robots: {e}")

        if active_robot:
            tmpl = active_robot.get("msg_template", "")
            if tmpl and raw_text:
                data.update(self._smart_parse(raw_text, tmpl))

            mm_mode = active_robot.get("mm_mode", "Fisso (€)")
            stake_val = float(active_robot.get("stake_value", 5.0))
            
            if "Roserpina" in mm_mode:
                bankroll = self.money_manager.bankroll()
                dynamic_stake = max(2.0, bankroll * 0.02)
                self.money_manager.current_stake = float(f"{dynamic_stake:.2f}")
                self.log_message.emit(f"📉 ROSERPINA: Calcolato {self.money_manager.current_stake}€ (2% di {bankroll})")
            else:
                self.money_manager.current_stake = stake_val

            if not data.get("teams"): data["teams"] = "Match Fallback" # Evita crash se il parse fallisce
            if not data.get("market"): data["market"] = "Winner"

            self.worker.submit(self.engine.process_signal, data, self.money_manager)

    def _on_bet_success(self, payload):
        with self._lock:
            self.fail_count = 0
            self.circuit_open = False
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
