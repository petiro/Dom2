import logging
import threading
import time
import yaml
import os
import json
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
        
        self.worker.executor = DomExecutorPlaywright(logger=logger, allow_place=allow_bets)
        self.engine = ExecutionEngine(bus, self.worker.executor, logger)
        
        # Lock Logico per Race Conditions
        self.bet_in_progress = False
        self.circuit_open = False
        self._lock = threading.Lock()
        
        bus.subscribe("BET_SUCCESS", self._on_bet_success)
        bus.subscribe("BET_FAILED", self._on_bet_failed)
        self.worker.start()
        bus.start()
        
        # Loop Watchdog Esiti
        threading.Thread(target=self._settled_bets_watchdog, daemon=True).start()

    # --- INTEGRAZIONE AI (OPENROUTER CON FALLBACK) ---
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
        
        # 🟢 LISTA DI FALLBACK AGGIORNATA (Trinity in cima come scelta più stabile)
        MODELS = [
            "arcee-ai/trinity-large-preview:free",            # 🔥 1° SCELTA: Più stabile e sempre online
            "google/gemini-2.0-flash-lite-preview-02-05:free",# 2° Scelta
            "openai/gpt-oss-120b:free",                       # 3° Scelta
            "qwen/qwen-3-coder-480b-a35b-instruct:free",      # 4° Scelta
            "meta-llama/llama-3.3-70b-instruct:free",         # 5° Scelta
            "stepfun/step-3.5-flash:free"                     # Estrema ratio
        ]

        # Se hai forzato un modello specifico nel config.yaml, quello vince su tutti
        config_model = self.config.get("openrouter", {}).get("model")
        if config_model and config_model not in MODELS:
            MODELS.insert(0, config_model)

        success = False
        headers = {
            "Authorization": f"Bearer {api_key}", 
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/v4-agent" # Obbligatorio per i modelli free
        }

        # 🟢 LOOP DI TENTATIVI INTELLIGENTE
        for model in MODELS:
            try:
                self.logger.info(f"🔄 AI: Tentativo parsing con modello {model}...")
                payload = {
                    "model": model, 
                    "messages": [{"role": "user", "content": prompt}]
                }
                
                resp = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload, timeout=12)
                
                if resp.status_code == 200:
                    ai_reply = resp.json()['choices'][0]['message']['content']
                    self.ai_analysis_ready.emit(f"✅ (Modello usato: {model})\n\n{ai_reply}")
                    success = True
                    break # Successo: esce dal loop immediatamente
                
                elif resp.status_code == 429:
                    self.logger.warning(f"⏳ AI: Modello {model} intasato (429). Passo al prossimo...")
                    time.sleep(1)
                    continue
                else:
                    self.logger.error(f"❌ AI: Modello {model} ha dato errore {resp.status_code}.")
                    continue
                    
            except Exception as e:
                self.logger.warning(f"⚠️ AI: Eccezione/Timeout con {model}: {e}")
                continue

        # Se la sfortuna vuole che TUTTI i modelli siano offline
        if not success:
            self.ai_analysis_ready.emit("❌ ERRORE CRITICO: Tutti i modelli AI gratuiti sono occupati o offline. Riprova tra poco.")

    # --- PARSING E GESTIONE SEGNALI ---
    def fallback_parse(self, msg):
        m = re.search(r'(\d+)\s*-\s*(\d+)', msg)
        if m:
            return {"score": f"{m.group(1)}-{m.group(2)}", "market": "Winner"}
        return None

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

        # BLOCCO RACE CONDITION: Se in corso, scarta.
        with self._lock:
            if self.bet_in_progress:
                self.logger.warning("⚠️ Bet in corso. Ignoro nuovo segnale.")
                return
            self.bet_in_progress = True

        try:
            raw_text = data.get("raw_text", "")
            chat_id = data.get("chat_id", "")
            active_robot = None

            # 1. Trova il Robot attivo
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
                except Exception as e:
                    self.logger.error(f"Errore robots: {e}")

            # 2. Configura Dati e Money Management
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

            # 3. Fallback Parsing per dati base mancanti
            if not data.get("teams") or not data.get("market"):
                fallback_data = self.fallback_parse(data.get("raw_text", ""))
                if fallback_data: data.update(fallback_data)
                
            # Sicurezza finale anti-crash
            if not data.get("teams"): data["teams"] = "Match Fallback"
            if not data.get("market"): data["market"] = "Winner"

            # 4. Invia all'Engine
            self.worker.submit(self.engine.process_signal, data, self.money_manager)

        except Exception as e:
            # Rilascio manuale se fallisce prima dell'inserimento nel worker
            with self._lock: self.bet_in_progress = False
            self.logger.error(f"Errore handle_signal: {e}")

    # --- CALLBACKS E WATCHDOG ---
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