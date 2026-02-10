"""
SuperAgent V4 - Main Entry Point (SplashScreen + Async Boot)
Async bootloader: shows SplashScreen while lazy-importing modules in background.
Creates executor singleton, HealthMonitor, StateManager, AITrainerEngine,
SuperAgentController, SystemWatchdog, injects everything into UI.
"""
import os
import sys
import time
import logging
import threading
import ctypes

# --- SISTEMA AUTO-LOG (Scatola Nera) ---
def setup_logging():
    log_path = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), "debug_log.txt")
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # Rimuovi handler esistenti per evitare duplicati
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # File Handler con encoding corretto
    file_handler = logging.FileHandler(log_path, encoding='utf-8')
    file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))

    # Stream Handler per la console
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(logging.Formatter('%(levelname)s: %(message)s'))

    root_logger.addHandler(file_handler)
    root_logger.addHandler(stream_handler)

    logging.info("--- LOGGING INIZIALIZZATO CORRETTAMENTE ---")

# ---------------------------------------

def is_admin():
    if sys.platform != "win32":
        return True
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        return False

# PATCH 1 — Path stabile (before any local imports)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from PySide6.QtWidgets import QApplication, QSplashScreen, QLabel
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QPixmap, QFont, QColor

last_heartbeat = 0

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
    root = logging.getLogger()
    root.addHandler(file_handler)
    return logging.getLogger("SuperAgent")


def load_config():
    import yaml
    config_path = os.path.join(BASE_DIR, "config", "config.yaml")
    if not os.path.exists(config_path):
        return {}
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


# ---------------------------------------------------------------------------
#  V4: System Boot Thread — lazy imports in background
# ---------------------------------------------------------------------------
class SystemBootThread(QThread):
    """Background thread that initializes all heavy modules while SplashScreen shows.
    Emits progress updates and completion signal with all components."""

    progress = Signal(str)
    boot_complete = Signal(dict)  # emits dict of all initialized components

    def __init__(self, config, logger):
        super().__init__()
        self.config = config
        self.logger = logger

    def run(self):
        components = {}

        # 1. Config validation
        self.progress.emit("Validating config...")
        try:
            from ui.desktop_app import ConfigValidator
            errors = ConfigValidator.validate(self.config, self.logger)
            if errors:
                self.logger.warning(f"Config has {len(errors)} issue(s)")
        except Exception as e:
            self.logger.error(f"Config validation failed: {e}")

        # 2. AI initialization (ai/ modules removed — placeholders for future re-integration)
        self.progress.emit("Initializing AI engines...")
        vision = None
        telegram_learner = None
        self.logger.info("AI modules not available (ai/ removed) — skipping")
        components["vision"] = vision
        components["telegram_learner"] = telegram_learner

        # 3. RPA Healer (ai/ modules removed)
        rpa_healer = None
        components["rpa_healer"] = rpa_healer

        # 4. Kill Chrome + Executor
        self.progress.emit("Initializing browser executor...")
        executor = None
        try:
            from core.dom_executor_playwright import DomExecutorPlaywright, close_chrome
            close_chrome()
            rpa_cfg = self.config.get("rpa", {})
            executor = DomExecutorPlaywright(
                logger=self.logger,
                allow_place=rpa_cfg.get("allow_place", False),
                pin=rpa_cfg.get("pin", "0503"),
                headless=rpa_cfg.get("headless", False),
                use_real_chrome=rpa_cfg.get("use_real_chrome", True),
                chrome_profile=rpa_cfg.get("chrome_profile", "Default"),
            )
            stealth = rpa_cfg.get("stealth_mode", "balanced")
            executor.stealth_mode = stealth
            if rpa_healer:
                executor.set_healer(rpa_healer)
        except Exception as e:
            self.logger.error(f"Executor init failed: {e}")
        components["executor"] = executor

        # 5. Health Monitor
        self.progress.emit("Starting health monitor...")
        monitor = None
        try:
            from core.health import HealthMonitor
            monitor = HealthMonitor(self.logger, executor)
            monitor.run_forever()
        except Exception as e:
            self.logger.error(f"HealthMonitor init failed: {e}")
        components["monitor"] = monitor

        # 6. AI Trainer
        self.progress.emit("Initializing AI Trainer...")
        trainer = None
        try:
            from core.ai_trainer import AITrainerEngine
            trainer = AITrainerEngine(vision_learner=vision, logger=self.logger)
            if executor:
                trainer.set_executor(executor)
            if executor:
                executor.set_trainer(trainer)
        except Exception as e:
            self.logger.error(f"AITrainer init failed: {e}")
        components["trainer"] = trainer

        # 7. Controller
        self.progress.emit("Starting V4 Controller...")
        controller = None
        try:
            from core.controller import SuperAgentController
            controller = SuperAgentController(self.logger, self.config)
            controller.set_executor(executor)
            controller.set_trainer(trainer)
            controller.set_monitor(monitor)
            controller.set_vision(vision)
            controller.set_telegram_learner(telegram_learner)
            controller.set_rpa_healer(rpa_healer)
            controller.boot()
            # Wire CommandParser
            try:
                from core.command_parser import CommandParser
                cmd_parser = CommandParser(self.logger, self.config)
                controller.set_command_parser(cmd_parser)
            except Exception as e:
                self.logger.warning(f"CommandParser init failed: {e}")
        except Exception as e:
            self.logger.error(f"Controller init failed: {e}")
        components["controller"] = controller

        # 8. System Watchdog (wired to controller for browser recovery)
        self.progress.emit("Starting system watchdog...")
        watchdog = None
        try:
            from core.lifecycle import SystemWatchdog
            watchdog = SystemWatchdog(check_interval=30)
            # V4: Wire watchdog signals to controller
            if controller:
                controller.set_watchdog(watchdog)
            watchdog.start()
        except Exception as e:
            self.logger.error(f"SystemWatchdog init failed: {e}")
        components["watchdog"] = watchdog

        self.progress.emit("Boot complete!")
        self.logger.info("SUPERAGENT V4 BOOT COMPLETE — all systems initialized")
        self.boot_complete.emit(components)


def main():
    logger = setup_logger()
    logger.info("SUPERAGENT V4 STARTUP (H24 MODE)")

    config = load_config()

    # Create QApplication first (required for SplashScreen)
    app = QApplication(sys.argv)
    app.setApplicationName("SuperAgent")

    # Apply dark theme
    from ui.desktop_app import apply_dark_theme
    apply_dark_theme(app)

    # V4: SplashScreen while booting
    splash_pix = QPixmap(480, 280)
    splash_pix.fill(QColor(30, 30, 30))
    splash = QSplashScreen(splash_pix)
    splash.setFont(QFont("Arial", 14))
    splash.showMessage(
        "SuperAgent V4 — Starting...",
        Qt.AlignBottom | Qt.AlignCenter,
        QColor(42, 130, 218),
    )
    splash.show()
    app.processEvents()

    # Boot thread results container
    boot_result = {}
    boot_done = threading.Event()

    def on_progress(msg):
        splash.showMessage(
            f"SuperAgent V4 — {msg}",
            Qt.AlignBottom | Qt.AlignCenter,
            QColor(42, 130, 218),
        )
        app.processEvents()

    def on_boot_complete(components):
        nonlocal boot_result
        boot_result.update(components)
        boot_done.set()

    # Start background boot
    boot_thread = SystemBootThread(config, logger)
    boot_thread.progress.connect(on_progress)
    boot_thread.boot_complete.connect(on_boot_complete)
    boot_thread.start()

    # Process events while waiting for boot
    while not boot_done.is_set():
        app.processEvents()
        boot_done.wait(0.05)

    boot_thread.wait()  # ensure thread finished

    # Extract components
    vision = boot_result.get("vision")
    telegram_learner = boot_result.get("telegram_learner")
    rpa_healer = boot_result.get("rpa_healer")
    executor = boot_result.get("executor")
    monitor = boot_result.get("monitor")
    controller = boot_result.get("controller")

    # Create and show main window
    from ui.desktop_app import MainWindow
    window = MainWindow(
        vision=vision,
        telegram_learner=telegram_learner,
        rpa_healer=rpa_healer,
        logger=logger,
        executor=executor,
        config=config,
        monitor=monitor,
        controller=controller,
    )
    window.show()
    splash.finish(window)

    logger.info("SuperAgent V4 UI visible — entering event loop")

    try:
        sys.exit(app.exec())
    finally:
        if controller:
            try:
                controller.shutdown()
            except Exception:
                pass
        if executor:
            try:
                executor.close()
            except Exception:
                pass
        # Stop watchdog
        watchdog = boot_result.get("watchdog")
        if watchdog:
            try:
                watchdog.stop()
                watchdog.quit()
                watchdog.wait(3000)
            except Exception:
                pass


if __name__ == "__main__":
    setup_logging()
    if not is_admin():
        logging.warning("Avvio senza privilegi Admin - Alcune funzioni mouse/tastiera potrebbero fallire.")
    main()
