import threading
import logging
import json
import os
from datetime import datetime
from PySide6.QtCore import QObject, Signal
from core.money_management import MoneyManager
from core.signal_parser import TelegramSignalParser

# Path History
_ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HISTORY_FILE = os.path.join(_ROOT_DIR, "config", "bet_history.json")

class SuperAgentController(QObject):
    log_message = Signal(str)
    
    def __init__(self, logger_instance, config=None):
        super().__init__()
        self.logger = logger_instance
        self.money_manager = MoneyManager()
        self.parser = TelegramSignalParser()
        self.executor = None
        self._history = self._load_history()
        self._lock = threading.Lock()

    def set_executor(self, ex): self.executor = ex
    
    def set_live_mode(self, enabled):
        if self.executor: self.executor.set_live_mode(enabled)

    def reload_money_manager(self):
        self.money_manager.reload()
        self.logger.info("💰 Configurazione Money Management ricaricata.")

    def handle_telegram_signal(self, text):
        data = self.parser.parse(text)
        if not data.get("teams"): return
        
        self.logger.info(f"📩 Segnale: {data['teams']} ({data['market']})")
        threading.Thread(target=self._process_bet, args=(data,), daemon=True).start()

    def _process_bet(self, data):
        if not self.executor: return
        
        # 1. Ottieni Quota (Simulata o letta dall'executor)
        odds = 2.0 # In futuro: self.executor.get_live_odds()
        
        # 2. Calcola Stake
        stake = self.money_manager.get_stake(odds)
        strategy = self.money_manager.strategy
        
        if stake <= 0:
            self.logger.warning("⚠️ Stake calcolato 0 o nullo. Salto.")
            return

        # 3. Piazza & Verifica
        success = self.executor.place_bet(data["teams"], data["market"], stake)
        
        # 4. Salva in Storico
        record = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "teams": data["teams"],
            "market": data["market"],
            "stake": stake,
            "odds": odds,
            "strategy": strategy,
            "status": "CONFERMATA" if success else "FALLITA",
            "real_placement": self.executor.allow_place
        }
        
        self._save_to_history(record)
        
        if success:
            msg = f"✅ SCOMMESSA PIAZZATA E VERIFICATA: {stake}€ su {data['teams']}"
            self.logger.info(msg)
            self.safe_emit(self.log_message, msg)
        else:
            msg = f"❌ SCOMMESSA FALLITA: {data['teams']}"
            self.logger.error(msg)
            self.safe_emit(self.log_message, msg)

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
    def safe_emit(self, sig, msg): 
        try: sig.emit(msg)
        except: pass
    
    # Metodi vuoti per compatibilità UI
    def shutdown(self): pass
    def request_training(self): pass
    def request_auto_mapping(self, u): pass
