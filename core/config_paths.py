import os
import sys
from pathlib import Path

def get_project_root() -> Path:
    """Restituisce il percorso assoluto della root, compatibile con PyInstaller."""
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    try:
        return Path(__file__).resolve().parent.parent
    except (NameError, TypeError):
        return Path.cwd()

# --- PERCORSI BASE ---
ROOT_DIR = get_project_root()
CONFIG_DIR = ROOT_DIR / "config"
DATA_DIR = ROOT_DIR / "data"
LOGS_DIR = ROOT_DIR / "logs"

# --- FILE DI CONFIGURAZIONE ---
CONFIG_FILE = CONFIG_DIR / "config.yaml"
SELECTORS_FILE = CONFIG_DIR / "selectors.yaml"
VAULT_FILE = CONFIG_DIR / "vault.bin"
HISTORY_FILE = CONFIG_DIR / "bet_history.json"
MONEY_CONFIG_FILE = CONFIG_DIR / "money_config.json"
ROSERPINA_STATE_FILE = CONFIG_DIR / "roserpina_real_state.json"
ROBOTS_FILE = CONFIG_DIR / "my_robots.json"

# --- ASSETS ---
CHROME_ICON = DATA_DIR / "chrome_icon.png"

# --- COSTANTI DI TIMEOUT (Fix Low Priority) ---
TIMEOUT_SHORT = 3000
TIMEOUT_MEDIUM = 7000
TIMEOUT_LONG = 20000
