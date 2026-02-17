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
from core.event_bus import bus  # Importiamo il bus globale per lo stop

def main():
    # 1. Protezione Multiprocessing (Necessario per PyInstaller/Windows)
    multiprocessing.freeze_support()

    # FIX: QApplication DEVE essere creata PRIMA di qualsiasi QObject
    app = QApplication.instance() or QApplication(sys.argv)

    # 2. Setup Logger
    logger, log_signaler = setup_logger()
    logger.info("🚀 MAIN: Inizializzazione architettura V8.3 Cluster...")

    try:
        # Configurazione base per la UI
        config = {
            "telegram": {},
            "rpa": {"cdp_watchdog": True}
        }

        # 3. Inizializzazione Controller (V8 Architecture)
        # Il Controller ora si inizializza autonomamente (crea Worker, Executor, DB)
        # Non passiamo più 'config' qui perché usa i file interni
        controller = SuperAgentController(logger)
        
        # Recuperiamo l'executor creato internamente dal controller
        # per passarlo agli strumenti di monitoraggio e alla UI
        executor = controller.worker.executor
        
        # 4. Componenti Ausiliari
        trainer = AITrainerEngine(logger=logger)
        trainer.set_executor(executor)  # Colleghiamo l'executor al trainer
        
        monitor = HealthMonitor(logger, executor)
        watchdog = SystemWatchdog(executor=executor, logger=logger)
        parser = CommandParser(logger)

        # Nota: Non usiamo più controller.set_executor() o start_system() 
        # perché il Controller V8 è autonomo e si avvia nel suo __init__.

        # 5. Avvio Monitoraggio Esterno
        monitor.start()
        watchdog.start()

        # 6. Avvio UI
        # Passiamo l'executor e il controller alla UI
        exit_code = run_app(
            logger=logger,
            executor=executor,
            config=config,
            monitor=monitor,
            controller=controller
        )

        # 7. Chiusura Pulita
        logger.info("🔻 Chiusura Main...")
        
        # Shutdown per architettura V8
        if hasattr(controller, 'worker'):
            controller.worker.stop()
        
        bus.stop()  # Ferma l'EventBus globale
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