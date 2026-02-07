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
        # Se non riceve battiti per più di 5 minuti, forza il restart
        if time.time() - last_heartbeat > 300:
            logger.critical("🚨 SISTEMA BLOCCATO (FREEZE) RILEVATO! Riavvio forzato...")
            # Riavvia il processo attuale
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
        logger.warning("⚠️ API Key di OpenRouter mancante o non valida!")
        return False
    return True

def initialize_ai(config, logger):
    """Inizializza i componenti AI (Vision e Telegram)."""
    from ai.vision_learner import VisionLearner
    from ai.telegram_learner import TelegramLearner

    api_key = config.get("openrouter", {}).get("api_key")
    if not api_key:
        return None, None

    vision = VisionLearner(api_key=api_key, logger=logger)
    telegram_learner = TelegramLearner(vision_learner=vision, logger=logger)
    return vision, telegram_learner

def main():
    # 0. KILL CHROME PREVENTIVO
    # Libera il profilo per permettere a Playwright di agganciarsi
    close_chrome()

    logger = setup_logger()
    logger.info("=" * 40)
    logger.info("🚀 SUPERAGENT STARTUP (H24 MODE)")
    logger.info("=" * 40)

    # 1. CARICAMENTO E VALIDAZIONE CONFIG
    config = load_config()
    if config is None:
        logger.error("❌ config.yaml MANCANTE! Impossibile procedere.")
        return

    validate_config(config, logger)

    # 2. AVVIO MONITORAGGIO (IMMORTALITY LAYER)
    threading.Thread(target=heartbeat_worker, daemon=True).start()
    threading.Thread(target=freeze_monitor, args=(logger,), daemon=True).start()

    # 3. INIZIALIZZAZIONE AI
    vision, telegram_learner = initialize_ai(config, logger)

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

    # 5. INIZIALIZZAZIONE EXECUTOR SINGLETON (GHOST MODE)
    # Creato una sola volta per tutto il ciclo di vita dell'app
    executor = None
    try:
        executor = DomExecutorPlaywright(
            logger=logger,
            allow_place=config.get("rpa", {}).get("allow_place", False),
            pin=config.get("rpa", {}).get("pin", "0503"),
            use_real_chrome=True # Forza l'uso del tuo Chrome reale
        )
        if rpa_healer:
            executor.set_healer(rpa_healer)
        logger.info("✅ Singleton DomExecutor pronto (Stealth Mode)")
    except Exception as e:
        logger.error(f"DomExecutor init failed: {e}")

    # 6. AVVIO UI (Iniezione dipendenze)
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
        # Questo cattura errori fatali fuori dal main loop per il watchdog
        print(f"FATAL ERROR: {e}")
        sys.exit(1)
