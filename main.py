import sys
import os
import logging
import multiprocessing

# PySide6 imports
from PySide6.QtWidgets import QApplication
from ui.desktop_app import run_app

# Core imports
from core.controller import SuperAgentController
from core.dom_executor_playwright import DomExecutorPlaywright
from core.ai_trainer import AITrainerEngine
from core.health import HealthMonitor, SystemWatchdog
from core.command_parser import CommandParser
from core.logger import setup_logger # <--- Importa il nuovo logger

def main():
    # 1. Protezione Multiprocessing
    multiprocessing.freeze_support()
    
    # 2. Setup Logger (Crea il file)
    # logger: Oggetto per scrivere su file
    # log_signaler: Oggetto per mandare i log alla UI
    logger, log_signaler = setup_logger()
    
    logger.info("🚀 MAIN: Inizializzazione componenti...")

    try:
        app = QApplication(sys.argv)

        config = {
            "telegram": {}, 
            "rpa": {"cdp_watchdog": True}
        }

        # 3. Passiamo il logger al Controller
        controller = SuperAgentController(logger, config)

        # 4. Passiamo il logger all'Executor
        executor = DomExecutorPlaywright(logger, headless=False, use_real_chrome=True)
        controller.set_executor(executor)

        # Trainer
        trainer = AITrainerEngine() # Se il trainer usa log, passagli logger
        controller.set_trainer(trainer)

        # Monitor
        monitor = HealthMonitor(logger)
        controller.set_monitor(monitor)

        # Watchdog
        watchdog = SystemWatchdog()
        controller.set_watchdog(watchdog)
        
        # Parser
        parser = CommandParser(logger)
        controller.set_command_parser(parser)

        # Avvio Sistema
        controller.start_system()

        # 5. Avvio UI (Passiamo log_signaler per vedere i log a schermo)
        # Nota: Ho aggiunto log_signaler ai parametri di run_app se necessario,
        # ma per ora lo usiamo tramite i segnali del controller.
        
        # Colleghiamo il segnale del logger al controller per la UI
        # (Opzionale: se run_app gestisce i log diversamente)
        
        exit_code = run_app(
            logger=logger,
            executor=executor,
            config=config,
            monitor=monitor,
            controller=controller
        )

        logger.info("🔻 Chiusura Main...")
        controller.shutdown()
        sys.exit(exit_code)

    except Exception as e:
        # Se il logger è attivo usa quello, altrimenti print
        if 'logger' in locals():
            logger.critical(f"❌ ERRORE CRITICO MAIN: {e}", exc_info=True)
        else:
            print(f"CRITICAL ERROR: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
