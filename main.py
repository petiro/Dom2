"""
SuperAgent MERGED - Main Entry Point
Combines DomNativeAgent AI with Desktop UI
"""
import sys
import os
import logging
import yaml

# Add paths for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'ai'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'core'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'ui'))

from ui.desktop_app import run_app


def setup_logger():
    """Setup logging"""
    os.makedirs("logs", exist_ok=True)
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('logs/superagent.log'),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger("SuperAgent")


def load_config():
    """Load configuration"""
    config_path = "config/config.yaml"
    
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r') as f:
                return yaml.safe_load(f)
        except Exception as e:
            print(f"Error loading config: {e}")
    
    # Default config
    return {
        "openrouter": {
            "api_key": "",
            "model": "google/gemini-2.0-flash-exp:free"
        },
        "ui": {
            "theme": "dark",
            "auto_save": True
        },
        "rpa": {
            "enabled": False,
            "headless": True,
            "autobet": False
        }
    }


def initialize_ai(config, logger):
    """Initialize AI components"""
    api_key = config.get("openrouter", {}).get("api_key")
    
    if not api_key:
        logger.warning("No API key found. AI features will be limited.")
        logger.info("Add API key in Settings tab or config/config.yaml")
        return None, None
    
    try:
        from ai.vision_learner import VisionLearner
        from ai.telegram_learner import TelegramLearner
        
        # Vision learner
        vision = VisionLearner(
            api_key=api_key,
            model=config["openrouter"]["model"],
            logger=logger
        )
        
        logger.info("✅ Vision AI initialized")
        
        # Telegram learner (if enabled)
        telegram_learner = None
        if config.get("learning", {}).get("telegram", {}).get("enabled", True):
            telegram_learner = TelegramLearner(
                vision_learner=vision,
                logger=logger,
                min_confidence=config.get("learning", {}).get("telegram", {}).get("confidence_threshold", 0.75),
                min_examples_to_learn=config.get("learning", {}).get("telegram", {}).get("min_examples", 3)
            )
            logger.info("✅ Telegram learner initialized")
        
        logger.info("✅ AI components ready")
        return vision, telegram_learner
        
    except Exception as e:
        logger.error(f"Failed to initialize AI: {e}")
        return None, None


def print_banner(logger):
    """Print startup banner"""
    banner = """
╔═══════════════════════════════════════════════════════════════╗
║                                                               ║
║           🚀  SuperAgent - Intelligent RPA Desktop  🚀        ║
║                                                               ║
║  Features:                                                    ║
║  ✅ Desktop UI (PySide6)                                     ║
║  ✅ AI Chat Assistant                                        ║
║  ✅ Auto-learning (Telegram + RPA)                           ║
║  ✅ Self-healing selectors                                   ║
║  ✅ Vision AI                                                ║
║  ✅ Real-time monitoring                                     ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝
"""
    for line in banner.split('\n'):
        logger.info(line)


def main():
    """Main entry point"""
    # Setup
    logger = setup_logger()
    
    # Banner
    print_banner(logger)
    
    # Load config
    logger.info("📋 Loading configuration...")
    config = load_config()
    
    # Initialize AI
    logger.info("🧠 Initializing AI components...")
    vision, telegram_learner = initialize_ai(config, logger)
    
    if vision:
        logger.info("✅ AI ready")
        if telegram_learner:
            logger.info("✅ Telegram learning ready")
    else:
        logger.warning("⚠️ AI not initialized - running in limited mode")
        logger.info("💡 Add API key in Settings tab to enable AI features")
    
    # Start UI
    logger.info("🖥️ Starting desktop application...")
    
    try:
        sys.exit(run_app(vision, telegram_learner, None, logger))
    except KeyboardInterrupt:
        logger.info("Application stopped by user")
    except Exception as e:
        logger.error(f"Application error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
