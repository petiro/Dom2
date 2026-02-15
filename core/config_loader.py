import yaml
import os
import logging
from core.utils import get_project_root
from core.security import Vault


def load_secure_config(path=None):
    """Unisce la config pubblica (YAML) con i segreti criptati (Vault).

    IMP-05: I segreti vengono letti dal Vault criptato (AES-256),
    non piu da secrets.json in chiaro.
    """
    if path is None:
        path = os.path.join(get_project_root(), "config", "config.yaml")

    config = {}

    # 1. Carica Config Pubblica (YAML)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f) or {}
        except Exception as e:
            logging.getLogger("SuperAgent").error(f"Errore caricamento config.yaml: {e}")

    # 2. Carica Segreti dal Vault criptato
    try:
        vault = Vault()
        secrets = vault.decrypt_data()
        config.update(secrets)  # I segreti vincono sulla config base
    except Exception as e:
        logging.getLogger("SuperAgent").warning(f"Vault non disponibile: {e}")

    return config
