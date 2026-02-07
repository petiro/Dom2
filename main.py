"""
SuperAgent MERGED - Main Entry Point (Immortality & Singleton Edition)
Combina DomNativeAgent AI con Desktop UI e monitoraggio H24.
"""
import os
import sys
import time
import logging
import threading
import subprocess
from datetime import datetime

# PATCH 1 — Path stabile per exe e dev
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from ui.desktop_app import run_app
from core.dom_executor_playwright import DomExecutorPlaywright, close_chrome

# --- MONITORAGGIO HEARTBEAT (ANTI-FREEZE) ---
last_heartbeat = time.time()

def heartbeat_worker():
    """Aggiorna costantemente l'ultimo segno di vita."""
    global last_heartbeat
    while True:
        last_heartbeat = time.time()
        time.sleep(10)

def freeze_monitor(logger):
    """Controlla se il sistema si è bloccato (freeze logico)."""
    while True:
        time.sleep(30)
        if time.time() - last_heartbeat > 300:
            logger.critical("SISTEMA BLOCCATO (FREEZE) RILEVATO! Riavvio forzato...")
            os.execv(sys.executable, [sys.executable] + sys.argv)

def setup_logger():
    """Configura il logging professionale su file e console."""
    log_dir = os.path.join(BASE_DIR, "logs")
    os.makedirs(log_dir, exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(os.path.join(log_dir, 'superagent.log'), encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger("SuperAgent")

def load_config():
    """Carica la configurazione YAML con gestione errori."""
    import yaml
    config_path = os.path.join(BASE_DIR, "config", "config.yaml")

    if not os.path.exists(config_path):
        return None

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}

def validate_config(config, logger):
    """Verifica che le chiavi essenziali siano presenti."""
    api_key = config.get("openrouter", {}).get("api_key")
    if not api_key or "YOUR_KEY" in api_key:
        logger.warning("API Key di OpenRouter mancante o non valida!")
        return False
    return True

def initialize_ai(config, logger):
    """Inizializza i componenti AI (Vision e Telegram) con gestione errori robusta."""
    api_key = config.get("openrouter", {}).get("api_key")
    if not api_key or api_key == "INSERISCI_KEY":
        logger.warning("No API key found. AI features will be limited.")
        return None, None

    try:
        from ai.vision_learner import VisionLearner
        from ai.telegram_learner import TelegramLearner

        vision = VisionLearner(
            api_key=api_key,
            model=config.get("openrouter", {}).get("model", "google/gemini-2.0-flash-exp:free"),
            logger=logger
        )
        logger.info("Vision AI initialized")

        telegram_learner = None
        if config.get("learning", {}).get("telegram", {}).get("enabled", True):
            telegram_learner = TelegramLearner(
                vision_learner=vision,
                logger=logger,
                min_confidence=config.get("learning", {}).get("telegram", {}).get("confidence_threshold", 0.75),
                min_examples_to_learn=config.get("learning", {}).get("telegram", {}).get("min_examples", 3)
            )
            logger.info("Telegram learner initialized")

        return vision, telegram_learner
    except Exception as e:
        logger.error(f"Failed to initialize AI: {e}")
        return None, None


def create_executor(config, logger, rpa_healer=None):
    """Factory: crea il Singleton DomExecutor con tutta la config RPA."""
    try:
        rpa_cfg = config.get("rpa", {})
        executor = DomExecutorPlaywright(
            logger=logger,
            headless=rpa_cfg.get("headless", False),
            allow_place=rpa_cfg.get("allow_place", False),
            pin=rpa_cfg.get("pin", "0503"),
            use_real_chrome=rpa_cfg.get("use_real_chrome", True),
            chrome_profile=rpa_cfg.get("chrome_profile", "Default"),
        )
        if rpa_healer:
            executor.set_healer(rpa_healer)
        logger.info("Singleton DomExecutor pronto")
        return executor
    except Exception as e:
        logger.error(f"DomExecutor init failed: {e}")
        return None


def start_services():
    """Valida la config Telegram all'avvio."""
    try:
        from gateway.telegram_listener_fixed import validate_telegram_config
        validate_telegram_config()
        print("Telegram config validata")
    except Exception as e:
        print("Telegram non attivo:", e)


def main():
    # 0. KILL CHROME PREVENTIVO
    close_chrome()

    logger = setup_logger()
    logger.info("=" * 40)
    logger.info("SUPERAGENT STARTUP (H24 MODE)")
    logger.info("=" * 40)

    # 1. CARICAMENTO E VALIDAZIONE CONFIG
    config = load_config()
    if config is None:
        logger.error("config.yaml MANCANTE! Impossibile procedere.")
        return

    validate_config(config, logger)

    # 2. AVVIO MONITORAGGIO (IMMORTALITY LAYER)
    threading.Thread(target=heartbeat_worker, daemon=True).start()
    threading.Thread(target=freeze_monitor, args=(logger,), daemon=True).start()

    # 3. INIZIALIZZAZIONE AI
    vision, telegram_learner = initialize_ai(config, logger)

    # 3.5. VALIDAZIONE TELEGRAM
    start_services()

    # 4. INIZIALIZZAZIONE HEALER (AUTO-RIPARAZIONE)
    rpa_healer = None
    if vision and config.get("learning", {}).get("rpa_healing", {}).get("enabled", True):
        try:
            from ai.rpa_healer import RPAHealer
            rpa_healer = RPAHealer(
                vision_learner=vision,
                logger=logger,
                confidence_threshold=config.get("learning", {}).get("rpa_healing", {}).get("confidence_threshold", 0.8)
            )
        except Exception as e:
            logger.error(f"Healer init failed: {e}")

    # 5. INIZIALIZZAZIONE EXECUTOR SINGLETON
    executor = create_executor(config, logger, rpa_healer)

    # 6. AVVIO UI (Iniezione dipendenze — executor singleton passato alla UI)
    logger.info("Starting desktop application...")
    try:
        run_app(vision, telegram_learner, rpa_healer, logger, executor)
    except Exception as e:
        logger.critical(f"UI CRASH: {e}")
    finally:
        # Assicura la chiusura pulita delle risorse browser
        if executor:
            executor.close()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nChiusura manuale richiesta.")
    except Exception as e:
        print(f"FATAL ERROR: {e}")
        sys.exit(1)
