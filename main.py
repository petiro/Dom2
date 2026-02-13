import sys
import os
import logging
import threading
import multiprocessing

# PySide6 imports
from PySide6.QtWidgets import QApplication
from ui.desktop_app import run_app

# Core imports
from core.controller import SuperAgentController
from core.dom_executor_playwright import DomExecutorPlaywright
from core.ai_trainer import AITrainerEngine
# from core.anti_detect import AntiDetect  <-- RIMOSSO (Causava l'errore)
from core.telegram_worker import TelegramWorker
from core.health import HealthMonitor, SystemWatchdog
from core.money_management import RoserpinaTable
from core.command_parser import CommandParser
from core.logger import setup_logger

# Configurazione Logger Principale
logger, _ = setup_logger()

def main():
    # --- 1. PROTEZIONE MULTIPROCESSING (CRUCIALE PER EXE) ---
    multiprocessing.freeze_support()  # Blocca la clonazione infinita su Windows
    
    logger.info("🚀 AVVIO SISTEMA SUPERAGENT V5.6 SENTINEL...")

    # --- 2. Inizializzazione Core Components ---
    try:
        # Configurazione base
        config = {
            "telegram": {},  # Sarà caricato da UI/Controller
            "rpa": {"cdp_watchdog": True}  # Watchdog attivo ma controllato
        }

        # Istanza Controller (Cervello)
        controller = SuperAgentController(logger, config)

        # Istanza Executor (Braccio)
        # headless=False così vedi il browser
        executor = DomExecutorPlaywright(logger, headless=False, use_real_chrome=True)
        controller.set_executor(executor)

        # Istanza Trainer (Apprendimento)
        trainer = AITrainerEngine()
        controller.set_trainer(trainer)

        # Istanza Monitor (Salute)
        monitor = HealthMonitor(logger)
        controller.set_monitor(monitor)

        # Istanza Watchdog (Sicurezza)
        watchdog = SystemWatchdog()
        controller.set_watchdog(watchdog)
        
        # Parser Comandi
        parser = CommandParser(logger)
        controller.set_command_parser(parser)

        # Avvio Sistema (Boot Async)
        controller.start_system()

        # --- 3. Avvio Interfaccia Grafica (UI) ---
        # Passiamo tutti i componenti alla UI
        exit_code = run_app(
            vision=None, # Vision learner inizializzato on-demand
            telegram_learner=None,
            rpa_healer=None, # Gestito internamente
            logger=logger,
            executor=executor,
            config=config,
            monitor=monitor,
            controller=controller
        )

        # --- 4. Chiusura Pulita ---
        logger.info("🔻 Chiusura Main...")
        controller.shutdown()
        sys.exit(exit_code)

    except Exception as e:
        logger.critical(f"❌ ERRORE CRITICO ALL'AVVIO: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
