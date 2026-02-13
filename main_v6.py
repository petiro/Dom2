import sys
import os
import logging
import multiprocessing

# PySide6 imports
from PySide6.QtWidgets import QApplication
from ui.desktop_app import run_app  # Usa la funzione corretta da desktop_app

# Core imports
from core.controller import SuperAgentController
from core.dom_executor_playwright import DomExecutorPlaywright
from core.ai_trainer import AITrainerEngine
from core.health import HealthMonitor, SystemWatchdog
from core.command_parser import CommandParser
from core.logger import setup_logger

# Configurazione Logger Principale
logger, _ = setup_logger()

def main():
    # --- 1. PROTEZIONE MULTIPROCESSING ---
    multiprocessing.freeze_support()
    
    logger.info("🚀 AVVIO SISTEMA SUPERAGENT V5.6 (MAIN V6)...")

    # --- 2. Inizializzazione Core Components ---
    try:
        config = {
            "telegram": {}, 
            "rpa": {"cdp_watchdog": True}
        }

        # Controller
        controller = SuperAgentController(logger, config)

        # Executor
        executor = DomExecutorPlaywright(logger, headless=False, use_real_chrome=True)
        controller.set_executor(executor)

        # Trainer
        trainer = AITrainerEngine()
        controller.set_trainer(trainer)

        # Monitor & Watchdog
        monitor = HealthMonitor(logger)
        controller.set_monitor(monitor)

        watchdog = SystemWatchdog()
        controller.set_watchdog(watchdog)
        
        # Parser
        parser = CommandParser(logger)
        controller.set_command_parser(parser)

        # Avvio Sistema
        controller.start_system()

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
        sys.exit(exit_code)

    except Exception as e:
        logger.critical(f"❌ ERRORE CRITICO ALL'AVVIO V6: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
