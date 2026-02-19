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
        if not os.path.exists(self.config_path):
            os.makedirs(CONFIG_DIR, exist_ok=True)
            default_conf = {
                "system": {"version": "8.5", "debug_level": "info"},
                "openrouter": {"api_key": "", "model": "google/gemini-2.0-flash-lite-preview-02-05:free"},
                "betting": {"allow_place": False}
            }
            try:
                with open(self.config_path, "w") as f:
                    yaml.dump(default_conf, f)
            except Exception as e:
                self.logger.error(f"Errore config: {e}")

    def load_config(self):
        try:
            if not os.path.exists(self.config_path): self._ensure_config_exists()
            with open(self.config_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except Exception: return {}
