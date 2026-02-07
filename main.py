"""
SuperAgent MERGED - Main Entry Point (Immortality & Singleton Edition)
"""
import os
import sys
import time
import logging
import threading
from ui.desktop_app import run_app
from core.dom_executor_playwright import DomExecutorPlaywright, close_chrome

# PATCH 1 — Path stabile
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

# --- MONITORAGGIO HEARTBEAT ---
last_heartbeat = time.time()

def heartbeat_worker():
    global last_heartbeat
    while True:
        last_heartbeat = time.time()
        time.sleep(10)

def freeze_monitor(logger):
    while True:
        time.sleep(30)
        if time.time() - last_heartbeat > 300:  # 5 minuti di freeze
            logger.critical("🚨 FREEZE RILEVATO! Riavvio forzato...")
            os.execv(sys.executable, [sys.executable] + sys.argv)


def setup_logger():
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
    import yaml
    config_path = os.path.join(BASE_DIR, "config", "config.yaml")
    if not os.path.exists(config_path):
        return {}
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}

def main():
    # 1. KILL CHROME PREVENTIVO
    close_chrome()

    logger = setup_logger()
    logger.info("🚀 SUPERAGENT STARTUP (H24 MODE)")

    config = load_config()

    # 2. AVVIO MONITORAGGIO
    threading.Thread(target=heartbeat_worker, daemon=True).start()
    threading.Thread(target=freeze_monitor, args=(logger,), daemon=True).start()

    # 3. INIZIALIZZAZIONE AI
    from ai.vision_learner import VisionLearner
    from ai.telegram_learner import TelegramLearner
    vision = VisionLearner(api_key=config.get("openrouter", {}).get("api_key"), logger=logger)
    telegram_learner = TelegramLearner(vision_learner=vision, logger=logger)

    # 4. INIZIALIZZAZIONE HEALER
    rpa_healer = None
    try:
        from ai.rpa_healer import RPAHealer
        rpa_healer = RPAHealer(vision_learner=vision, logger=logger)
    except Exception as e:
        logger.error(f"Healer init failed: {e}")

    # 5. INIZIALIZZAZIONE EXECUTOR SINGLETON (L'UNICO)
    executor = None
    try:
        executor = DomExecutorPlaywright(
            logger=logger,
            allow_place=config.get("rpa", {}).get("allow_place", False),
            pin=config.get("rpa", {}).get("pin", "0503")
        )
        if rpa_healer:
            executor.set_healer(rpa_healer)
    except Exception as e:
        logger.error(f"Executor init failed: {e}")

    # 6. AVVIO UI CON INIEZIONE SINGLETON
    logger.info("Iniezione executor nella UI...")
    # AGGIORNATO: Passiamo l'executor come quinto parametro
    sys.exit(run_app(vision, telegram_learner, rpa_healer, logger, executor))

if __name__ == "__main__":
    main()
