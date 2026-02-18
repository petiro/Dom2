import yaml
import os
import logging
from core.config_paths import CONFIG_FILE, CONFIG_DIR

class ConfigLoader:
    def __init__(self, logger=None):
        self.logger = logger or logging.getLogger("ConfigLoader")
        self.config_path = CONFIG_FILE
        self._ensure_config_exists()

    def _ensure_config_exists(self):
        """Crea un config di default se non esiste"""
        if not os.path.exists(self.config_path):
            os.makedirs(CONFIG_DIR, exist_ok=True)
            default_conf = {
                "system": {"version": "8.4", "debug_level": "info"},
                "telegram": {"api_id": "", "api_hash": "", "phone": ""},
                "betting": {
                    "allow_place": False,  # Default Safe Mode
                    "stake_amount": 10.0,
                    "max_daily_loss": 50.0
                },
                "rpa": {"headless": False, "enabled": True}
            }
            try:
                with open(self.config_path, "w") as f:
                    yaml.dump(default_conf, f)
                self.logger.info(f"🆕 Config creato in: {self.config_path}")
            except Exception as e:
                self.logger.error(f"Errore creazione config default: {e}")

    def load_config(self):
        """Carica e restituisce il dizionario di configurazione"""
        try:
            if not os.path.exists(self.config_path):
                self._ensure_config_exists()
                
            with open(self.config_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            self.logger.error(f"❌ Errore caricamento config: {e}")
            return {}

    def save_config(self, new_config):
        """Salva il dizionario su disco"""
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                yaml.dump(new_config, f)
            self.logger.info("✅ Configurazione salvata.")
            return True
        except Exception as e:
            self.logger.error(f"❌ Errore salvataggio config: {e}")
            return False