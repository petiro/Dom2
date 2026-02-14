import threading
import logging
import json
import os
import time
from datetime import datetime
from PySide6.QtCore import QObject, Signal

# Import dei moduli Core
from core.money_management import MoneyManager
from core.ai_parser import AISignalParser
# Importa il loader sicuro
from core.config_loader import load_secure_config
try: from core.signal_parser import TelegramSignalParser
except: TelegramSignalParser = None

# Percorsi
_ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HISTORY_FILE = os.path.join(_ROOT_DIR, "config", "bet_history.json")

class SuperAgentController(QObject):
    log_message = Signal(str)
    
    def __init__(self, logger_instance, config=None):
        super().__init__()
        self.logger = logger_instance
        self.config = config
        
        # 1. CARICAMENTO SICURO CHIAVI
        self.secrets = load_secure_config()
        api_key = self.secrets.get("openrouter_api_key")
        
        if not api_key:
            self.logger.warning("⚠️ ATTENZIONE: Nessuna chiave OpenRouter trovata. L'AI potrebbe non funzionare.")
        else:
            self.logger.info("🔑 Chiavi API caricate con successo.")

        # 2. Inizializza AI con la chiave caricata
        self.ai_parser = AISignalParser(api_key=api_key)
        
        # 3. Altri componenti
        self.money_manager = MoneyManager()
        self.legacy_parser = TelegramSignalParser() if TelegramSignalParser else None
        
        # Componenti da collegare
        self.executor = None
        self.trainer = None
        self.monitor = None
        self.watchdog = None
        self.command_parser = None
        
        self._history = self._load_history()
        
        # --- THREAD WATCHDOG ---
        self._lock = threading.Lock()
        self._active_threads = 0
        self._stop_event = threading.Event()

    # --- METODI DI COLLEGAMENTO (FIX PER MAIN.PY) ---
    def set_executor(self, ex): self.executor = ex
    def set_trainer(self, trainer): self.trainer = trainer
    def set_monitor(self, monitor): self.monitor = monitor
    def set_watchdog(self, watchdog): self.watchdog = watchdog
    def set_command_parser(self, parser): self.command_parser = parser

    def start_system(self):
        """Chiamato da main.py per avviare eventuali thread di background"""
        self.logger.info("✅ Controller avviato. In attesa di segnali.")

    # --- LOGICA OPERATIVA ---
    def set_live_mode(self, enabled):
        if self.executor: self.executor.set_live_mode(enabled)

    def reload_money_manager(self):
        self.money_manager.reload()
        self.logger.info("💰 [CONTROLLER] Configurazione Money Management ricaricata.")

    def reload_secrets(self):
        """Metodo chiamato dalla UI quando si salvano nuove chiavi"""
        from core.config_loader import load_secure_config
        self.secrets = load_secure_config()
        
        # Aggiorna la chiave dell'AI in tempo reale
        api_key = self.secrets.get("openrouter_api_key")
        if self.ai_parser:
            self.ai_parser.api_key = api_key
            
        self.logger.info("🔑 [CONTROLLER] Chiavi di sistema ricaricate dalla UI.")

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
            if (not data or not data.get("teams")) and self.legacy_parser:
                self.logger.info("🤖 AI incerta, uso parser classico...")
                data = self.legacy_parser.parse(text)

            if not data or not data.get("teams"):
                self.logger.warning("⚠️ Dati insufficienti nel segnale.")
                return

            self.logger.info(f"🎯 TARGET: {data['teams']} -> {data['market']}")
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
        # TODO: Implementare self.executor.get_live_odds()
        odds = 2.0 
        
        # 2. Calcola Stake
        stake = self.money_manager.get_stake(odds)
        strategy = getattr(self.money_manager, 'strategy', 'N/A')
        
        if stake <= 0.10:
            self.logger.warning("⚠️ Stake calcolato nullo o ciclo finito. Salto.")
            return

        # 3. Piazza & Verifica (Blocking Call, ma siamo in un thread quindi OK)
        success = self.executor.place_bet(data["teams"], data["market"], stake)
        
        # 4. Registra Esito (Nota: Roserpina reale richiederebbe esito post-partita)
        # self.money_manager.record_outcome("pending", stake, odds) 
        
        # 5. Salva Storico
        record = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "teams": data["teams"],
            "market": data["market"],
            "stake": stake,
            "odds": odds,
            "strategy": strategy,
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

    # --- STUBS RICHIESTI DALLA UI ---
    def shutdown(self): 
        self.logger.info("🔻 Controller Shutdown...")
        if self.executor: self.executor.close()
        
    def request_training(self): pass
    
    def request_auto_mapping(self, url):
        self.logger.info(f"🗺️ Richiesta mapping per: {url}")
        
    def process_robot_chat(self, robot_name, text):
        self.logger.info(f"💬 Chat robot {robot_name}: {text}")
        if hasattr(self, 'ui_window') and hasattr(self.ui_window, 'factory'):
            self.ui_window.factory.receive_ai_reply(robot_name, "Ricevuto. Sto imparando...")
