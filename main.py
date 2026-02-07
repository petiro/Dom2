"""
SuperAgent MERGED - Main Entry Point (Immortality & Singleton Edition)
Central orchestrator: creates executor singleton, HealthMonitor, injects into UI.
"""
import os
import sys
import time
import logging
import threading

# PATCH 1 — Path stabile (before any local imports)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from ui.desktop_app import run_app, ConfigValidator
from core.dom_executor_playwright import DomExecutorPlaywright, close_chrome
from core.health import HealthMonitor

# --- MONITORAGGIO HEARTBEAT (global, for backward compat) ---
last_heartbeat = time.time()


def setup_logger():
    from logging.handlers import RotatingFileHandler
    log_dir = os.path.join(BASE_DIR, "logs")
    os.makedirs(log_dir, exist_ok=True)
    fmt = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    # Rotating log: 5 MB per file, keep 5 backups (max ~25 MB total)
    file_handler = RotatingFileHandler(
        os.path.join(log_dir, 'superagent.log'),
        maxBytes=5_000_000,
        backupCount=5,
        encoding='utf-8',
    )
    file_handler.setFormatter(fmt)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(fmt)
    logging.basicConfig(
        level=logging.INFO,
        handlers=[file_handler, console_handler]
    )
    return logging.getLogger("SuperAgent")


def load_config():
    import yaml
    config_path = os.path.join(BASE_DIR, "config", "config.yaml")
    if not os.path.exists(config_path):
        return {}
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def create_executor(config, logger, rpa_healer=None):
    """Factory function: creates and configures the singleton DomExecutorPlaywright."""
    rpa_cfg = config.get("rpa", {})
    executor = DomExecutorPlaywright(
        logger=logger,
        allow_place=rpa_cfg.get("allow_place", False),
        pin=rpa_cfg.get("pin", "0503"),
        headless=rpa_cfg.get("headless", False),
        use_real_chrome=rpa_cfg.get("use_real_chrome", True),
        chrome_profile=rpa_cfg.get("chrome_profile", "Default"),
    )
    if rpa_healer:
        executor.set_healer(rpa_healer)
    return executor


def main():
    # 1. KILL CHROME PREVENTIVO
    close_chrome()

    logger = setup_logger()
    logger.info("SUPERAGENT STARTUP (H24 MODE)")

    config = load_config()

    # 1b. VALIDAZIONE CONFIG
    errors = ConfigValidator.validate(config, logger)
    if errors:
        logger.warning(f"Config has {len(errors)} issue(s) — app will start anyway")

    # 2. INIZIALIZZAZIONE AI
    vision = None
    telegram_learner = None
    try:
        from ai.vision_learner import VisionLearner
        from ai.telegram_learner import TelegramLearner
        vision = VisionLearner(api_key=config.get("openrouter", {}).get("api_key"), logger=logger)
        telegram_learner = TelegramLearner(vision_learner=vision, logger=logger)
    except Exception as e:
        logger.error(f"AI init failed: {e}")

    # 3. INIZIALIZZAZIONE HEALER
    rpa_healer = None
    try:
        from ai.rpa_healer import RPAHealer
        rpa_healer = RPAHealer(vision_learner=vision, logger=logger)
    except Exception as e:
        logger.error(f"Healer init failed: {e}")

    # 4. INIZIALIZZAZIONE EXECUTOR SINGLETON (L'UNICO)
    executor = None
    try:
        executor = create_executor(config, logger, rpa_healer)
    except Exception as e:
        logger.error(f"Executor init failed: {e}")

    # 5. HEALTH MONITOR — Centralised Immortality Layer
    monitor = HealthMonitor(logger, executor)
    monitor.run_forever()   # starts freeze detector, memory guard, maintenance restart

    # 6. AVVIO UI CON INIEZIONE SINGLETON + MONITOR
    logger.info("Iniezione executor + monitor nella UI...")
    try:
        sys.exit(run_app(
            vision, telegram_learner, rpa_healer,
            logger, executor, config, monitor
        ))
    finally:
        if executor:
            try:
                executor.close()
            except Exception:
                pass


if __name__ == "__main__":
    main()
