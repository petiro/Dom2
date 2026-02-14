import os
import json
import logging
import yaml

from core.utils import get_project_root

_ROOT_DIR = get_project_root()


def load_secrets():
    """Carica le chiavi sensibili dal file secrets.json locale."""
    secrets_path = os.path.join(_ROOT_DIR, "config", "secrets.json")

    if not os.path.exists(secrets_path):
        return {}

    try:
        with open(secrets_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return {k: str(v).strip() for k, v in data.items()}
    except Exception as e:
        logging.getLogger("SuperAgent").error(f"Errore lettura secrets.json: {e}")
        return {}


def load_secure_config():
    """Unisce config base YAML e secrets JSON. I secrets hanno priorita."""
    # FIX BUG-08: Usa percorso assoluto
    config_path = os.path.join(_ROOT_DIR, "config", "config.yaml")

    # 1. Carica secrets
    secrets = load_secrets()

    # 2. Carica config base (se esiste)
    config = {}
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f) or {}
        except Exception as e:
            logging.getLogger("SuperAgent").error(f"Errore caricamento config.yaml: {e}")

    # 3. Merge: i secrets vincono sempre
    config.update(secrets)
    return config
