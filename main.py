"""
SuperAgent MERGED - Main Entry Point
Combines DomNativeAgent AI with Desktop UI
"""
import os
import sys
import logging

# PATCH 1 — Path stabile per exe e dev
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from ui.desktop_app import run_app


def setup_logger():
    """Setup logging"""
    log_dir = os.path.join(BASE_DIR, "logs")
    os.makedirs(log_dir, exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(os.path.join(log_dir, 'superagent.log')),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger("SuperAgent")


# PATCH 2 — Caricamento config sicuro
def load_config():
    """Load configuration with safe path resolution"""
    import yaml
    config_path = os.path.join(BASE_DIR, "config", "config.yaml")

    if not os.path.exists(config_path):
        print("config.yaml mancante")
        return {}

    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def initialize_ai(config, logger):
    """Initialize AI components"""
    api_key = config.get("openrouter", {}).get("api_key")

    if not api_key or api_key == "INSERISCI_KEY":
        logger.warning("No API key found. AI features will be limited.")
        logger.info("Add API key in Settings tab or config/config.yaml")
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

        logger.info("AI components ready")
        return vision, telegram_learner

    except Exception as e:
        logger.error(f"Failed to initialize AI: {e}")
        return None, None


# PATCH 4 — Telegram collegato davvero
def start_services():
    """Start background services (Telegram listener, etc.)"""
    try:
        from gateway.telegram_listener_fixed import start_telegram_listener
        start_telegram_listener()
        print("Telegram listener avviato")
    except Exception as e:
        print("Telegram non attivo:", e)


def print_banner(logger):
    """Print startup banner"""
    banner = """
===============================================================
           SuperAgent - Intelligent RPA Desktop
===============================================================
  Desktop UI (PySide6)
  AI Chat Assistant
  Auto-learning (Telegram + RPA)
  Self-healing selectors
  Vision AI
  Real-time monitoring
===============================================================
"""
    for line in banner.strip().split('\n'):
        logger.info(line)


def main():
    """Main entry point"""
    logger = setup_logger()
    print_banner(logger)

    logger.info("Loading configuration...")
    config = load_config()

    logger.info("Initializing AI components...")
    vision, telegram_learner = initialize_ai(config, logger)

    if vision:
        logger.info("AI ready")
        if telegram_learner:
            logger.info("Telegram learning ready")
    else:
        logger.warning("AI not initialized - running in limited mode")
        logger.info("Add API key in Settings tab to enable AI features")

    # PATCH 4 — Avvia servizi prima della UI
    start_services()

    logger.info("Starting desktop application...")
    sys.exit(run_app(vision, telegram_learner, None, logger))


# PATCH 3 — Avvio UI sicuro con traceback visibile
if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("ERRORE AVVIO:", e)
        import traceback
        traceback.print_exc()
