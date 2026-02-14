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
        # WATCHDOG: Se ci sono tro
