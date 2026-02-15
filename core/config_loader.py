import yaml
import os
import logging
from core.utils import get_project_root
from core.security import Vault


def load_secure_config(path=None):
    """Merges public config (YAML) with encrypted secrets (Vault).

    Secrets are read from the encrypted Vault (AES-256).
    Vault secrets override base config values.
    """
    if path is None:
        path = os.path.join(get_project_root(), "config", "config.yaml")

    config = {}

    # 1. Load public config (YAML)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f) or {}
        except Exception as e:
            logging.getLogger("SuperAgent").error(f"Error loading config.yaml: {e}")

    # 2. Load secrets from encrypted Vault
    try:
        vault = Vault()
        secrets = vault.decrypt_data()
        config.update(secrets)
    except Exception as e:
        logging.getLogger("SuperAgent").warning(f"Vault unavailable: {e}")

    return config
