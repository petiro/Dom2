import threading
import logging
import json
import os
import time
from datetime import datetime
from PySide6.QtCore import QObject, Signal

from core.money_management import MoneyManager
from core.ai_parser import AISignalParser
# Se non hai signal_parser.py, rimuovi questa riga o usa un dummy
try: from core.signal_parser import TelegramSignalParser
except: TelegramSignalParser = None

_ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HISTORY_FILE = os.path.join(_ROOT_DIR, "config", "bet_history.json")

class SuperAgentController(QObject):
    log_message = Signal(str)
    
    def __init__(self, logger_instance, config=None):
        super().__init__()
        self.logger = logger_instance
        self.money_manager = MoneyManager()
        
        # Cervello AI
        self.ai_parser = AISignalParser()
        self.legacy_parser = TelegramSignalParser() if TelegramSignalParser else None
        
        self.executor = None
        self._history = self._load_history()
        self._lock = threading.Lock()
        self._active_thread = False

    def set_executor(self, ex): self.executor = ex
    def set_live_mode(self, enabled): 
        if self.executor: self.executor.set_live_mode(enabled)
    def reload_money_manager(self): 
        self.money_manager.reload()
        self.logger.info("💰 Money Manager aggiornato.")

    def handle_telegram_signal(self, text):
        if self._active_thread:
            self.logger.warning("⏳ BUSY: Operazione in corso. Segnale ignorato.")
            return
        
        self.logger.info("📩 RICEVUTO TELEGRAM. Analisi AI...")
        threading.Thread(target=self._process_signal, args=(text,), daemon=True).start()

    def _process_signal(self, text):
        self._active_thread = True
        try:
            # 1. ANALISI AI
            data = self.ai_parser.parse(text)
            
            # Fallback (opzionale)
            if not data.get("teams") and self.legacy_parser:
                self.logger.warning("⚠️ AI incerta, uso parser classico.")
                data = self.legacy_parser.parse(text)

            if not data.get("teams"):
                self.logger.error("❌ Nessun dato valido estratto.")
                return

            self.logger.info(f"🎯 TARGET: {data['teams']} -> {data['market']}")
            self._execute_bet(data)

        except Exception as e:
            self.logger.error(f"❌ Errore Thread: {e}")
        finally:
            self._active_thread = False

    def _execute_bet(self, data):
        if not self.executor: return

        # 1. Recupera Quota (Simulata 2.0 per ora)
        current_odds = 2.0 
        
        # 2. Calcola Stake
        stake = self.money_manager.get_stake(current_odds)
        if stake <= 0.10:
            self.logger.warning("⚠️ Stake troppo basso. Skip.")
            return

        # 3. PIAZZA & VERIFICA (Reale su Bet365)
        success = self.executor.place_bet(data["teams"], data["market"], stake)
        
        # 4. SALVA STORICO
        status = "CONFERMATA" if success else "FALLITA"
        record = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "teams": data["teams"],
            "market": data["market"],
            "stake": stake,
            "odds": current_odds,
            "status": status
        }
        self._save_to_history(record)
        
        if success:
            # Nota: Qui registriamo l'esito come 'pending' o 'lose' preventivo se necessario
            # Per Roserpina reale, l'esito va registrato DOPO la partita.
            self.logger.info(f"✅ BET OK: {stake}€ piazzati.")
            self.safe_emit(f"✅ BET OK: {stake}€ su {data['teams']}")
        else:
            self.logger.error("❌ BET FALLITA.")
            self.safe_emit(f"❌ BET KO: {data['teams']}")

    def _load_history(self):
        if os.path.exists(HISTORY_FILE):
            try: 
                with open(HISTORY_FILE, 'r') as f: return json.load(f)
            except: return []
        return []

    def _save_to_history(self, record):
        with self._lock:
            self._history.append(record)
            try:
                with open(HISTORY_FILE, 'w') as f: json.dump(self._history, f, indent=4)
            except: pass

    def get_bet_history(self): return self._history
    def safe_emit(self, msg): 
        try: self.log_message.emit(msg)
        except: pass

    # Stubs obbligatori
    def shutdown(self): 
        if self.executor: self.executor.close()
    def request_training(self): pass
    def request_auto_mapping(self, u): pass
    def process_robot_chat(self, n, t): pass
    def set_trainer(self, t): pass
    def set_monitor(self, m): pass
    def set_watchdog(self, w): pass
    def set_command_parser(self, c): pass
