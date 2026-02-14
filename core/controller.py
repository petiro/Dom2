import threading
import logging
import json
import os
import time
from datetime import datetime
from PySide6.QtCore import QObject, Signal
from core.money_management import MoneyManager
from core.signal_parser import TelegramSignalParser
from core.ai_parser import AISignalParser 

_ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HISTORY_FILE = os.path.join(_ROOT_DIR, "config", "bet_history.json")

class SuperAgentController(QObject):
    log_message = Signal(str)
    
    def __init__(self, logger_instance, config=None):
        super().__init__()
        self.logger = logger_instance
        self.money_manager = MoneyManager()
        
        # Selettore intelligente del parser
        self.ai_parser = AISignalParser() # Se hai la chiave, mettila qui o nel file
        self.simple_parser = TelegramSignalParser()
        
        self.executor = None
        self._history = self._load_history()
        
        # --- THREAD WATCHDOG ---
        self._lock = threading.Lock()
        self._active_threads = 0
        self._stop_event = threading.Event()

    def set_executor(self, ex): self.executor = ex
    
    def set_live_mode(self, enabled):
        if self.executor: self.executor.set_live_mode(enabled)

    def reload_money_manager(self):
        self.money_manager.reload()
        self.logger.info("💰 [CONTROLLER] Configurazione Money Management ricaricata.")

    def handle_telegram_signal(self, text):
        """
        Gestisce il segnale con protezione Threading.
        """
        # WATCHDOG: Se ci sono troppi thread attivi, ignora per evitare freeze
        with self._lock:
            if self._active_threads > 2:
                self.logger.warning("⚠️ [WATCHDOG] Troppe operazioni in corso. Segnale ignorato.")
                return
            self._active_threads += 1

        # Lancia il thread
        threading.Thread(target=self._process_signal_thread, args=(text,), daemon=True).start()

    def _process_signal_thread(self, text):
        try:
            self.logger.info("📩 Analisi messaggio in corso...")
            
            # 1. Prova AI Parser (più intelligente)
            data = self.ai_parser.parse(text)
            
            # 2. Fallback su Parser Semplice se AI fallisce o è vuota
            if not data or not data.get("teams"):
                self.logger.info("🤖 AI incerta, uso parser classico...")
                data = self.simple_parser.parse(text)

            if not data.get("teams"):
                self.logger.warning("⚠️ Dati insufficienti nel segnale.")
                return

            self._execute_bet_logic(data)
            
        except Exception as e:
            self.logger.error(f"❌ Errore thread segnale: {e}")
        finally:
            with self._lock:
                self._active_threads -= 1

    def _execute_bet_logic(self, data):
        if not self.executor: 
            self.logger.error("❌ Executor non collegato!")
            return

        # 1. Recupera Quota (Simulata o Live)
        odds = 2.0 # In futuro: self.executor.get_live_odds()
        
        # 2. Calcolo Stake
        stake = self.money_manager.get_stake(odds)
        strategy = self.money_manager.strategy
        
        if stake <= 0:
            self.logger.warning("⚠️ Stake calcolato 0. Salto.")
            return

        # 3. Piazza & Verifica (Blocking Call, ma siamo in un thread quindi OK)
        success = self.executor.place_bet(data["teams"], data["market"], stake)
        
        # 4. Registra Esito
        self.money_manager.record_outcome("win" if success else "lose", stake, odds) # Simuliamo esito immediato per test
        
        # 5. Salva Storico
        record = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "teams": data["teams"],
            "market": data["market"],
            "stake": stake,
            "status": "CONFERMATA" if success else "FALLITA"
        }
        self._save_to_history(record)
        
        if success:
            msg = f"✅ BET PIAZZATA: {stake}€ su {data['teams']}"
            self.logger.info(msg)
            self.safe_emit(msg)
        else:
            msg = f"❌ BET FALLITA: {data['teams']}"
            self.logger.error(msg)
            self.safe_emit(msg)

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
        """Emette il segnale UI in modo sicuro."""
        try: self.log_message.emit(msg)
        except: pass

    # Stubs per compatibilità
    def shutdown(self): 
        self.logger.info("🔻 Controller Shutdown...")
        if self.executor: self.executor.close()
    def request_training(self): pass
    def request_auto_mapping(self, u): pass
    def process_robot_chat(self, n, t): pass
