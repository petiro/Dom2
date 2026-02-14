import sys
import os
import logging
import multiprocessing

from PySide6.QtWidgets import QApplication
from ui.desktop_app import run_app

from core.controller import SuperAgentController
from core.dom_executor_playwright import DomExecutorPlaywright
from core.ai_trainer import AITrainerEngine
from core.health import HealthMonitor
from core.lifecycle import SystemWatchdog
from core.command_parser import CommandParser
from core.logger import setup_logger


def main():
    # --- 1. PROTEZIONE MULTIPROCESSING ---
    multiprocessing.freeze_support()

    # FIX BUG-05: QApplication PRIMA di qualsiasi QObject
    app = QApplication.instance() or QApplication(sys.argv)

    # Logger DOPO QApplication
    logger, _ = setup_logger()
    logger.info("🚀 AVVIO SISTEMA SUPERAGENT V5.6 (MAIN V6)...")

    # --- 2. Inizializzazione Core Components ---
    try:
        config = {
            "telegram": {},
            "rpa": {"cdp_watchdog": True}
        }

        controller = SuperAgentController(logger, config)
        executor = DomExecutorPlaywright(logger, headless=False, use_real_chrome=True)
        trainer = AITrainerEngine(logger=logger)
        monitor = HealthMonitor(logger, executor)
        watchdog = SystemWatchdog(executor=executor, logger=logger)
        parser = CommandParser(logger)

        controller.set_executor(executor)
        controller.set_trainer(trainer)
        controller.set_monitor(monitor)
        controller.set_watchdog(watchdog)
        controller.set_command_parser(parser)

        controller.start_system()
        monitor.start()
        watchdog.start()

        # --- 3. Avvio UI ---
        exit_code = run_app(
            logger=logger,
            executor=executor,
            config=config,
            monitor=monitor,
            controller=controller
        )

        # --- 4. Chiusura ---
        logger.info("🔻 Chiusura Main V6...")
        controller.shutdown()
        monitor.stop()
        watchdog.stop()
        sys.exit(exit_code)

    except Exception as e:
        logger.critical(f"❌ ERRORE CRITICO ALL'AVVIO V6: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
