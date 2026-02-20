import sys
import os
import logging
import multiprocessing

from PySide6.QtWidgets import QApplication
from ui.desktop_app import run_app

# Core imports
from core.controller import SuperAgentController
from core.ai_trainer import AITrainerEngine
from core.health import HealthMonitor
from core.lifecycle import SystemWatchdog
from core.command_parser import CommandParser
from core.logger import setup_logger
from core.event_bus import bus
from core.heartbeat import AppHeartbeat  # 🔴 IMPORT BATTITO CARDIACO

def main():
    multiprocessing.freeze_support()
    app = QApplication.instance() or QApplication(sys.argv)

    logger, log_signaler = setup_logger()
    logger.info("🚀 MAIN: Inizializzazione architettura ULTRA BUILD 11/10 (Hedge-Grade)...")

    # 🔴 AVVIO HEARTBEAT (Per il Supervisor OS-Level)
    AppHeartbeat.start()

    try:
        config = {
            "telegram": {},
            "rpa": {"cdp_watchdog": True}
        }

        controller = SuperAgentController(logger)
        executor = controller.worker.executor
        
        trainer = AITrainerEngine(logger=logger)
        trainer.set_executor(executor)
        
        monitor = HealthMonitor(logger, executor)
        watchdog = SystemWatchdog(executor=executor, logger=logger)
        parser = CommandParser(logger)

        monitor.start()
        watchdog.start()

        exit_code = run_app(
            logger=logger,
            executor=executor,
            config=config,
            monitor=monitor,
            controller=controller
        )

        logger.info("🔻 Chiusura Main...")
        if hasattr(controller, 'worker'):
            controller.worker.stop()
        
        bus.stop()
        monitor.stop()
        watchdog.stop()
        sys.exit(exit_code)

    except Exception as e:
        if 'logger' in locals():
            logger.critical(f"❌ ERRORE CRITICO MAIN: {e}", exc_info=True)
        else:
            print(f"CRITICAL ERROR: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()