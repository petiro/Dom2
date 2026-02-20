import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from PySide6.QtCore import QObject, Signal

# 🔴 IMPORTA IL FILTRO SEGRETI
from core.security_logger import SecretFilter

LOG_DIR = "logs"
LOG_FILE = "superagent.log"
MAX_BYTES = 5 * 1024 * 1024
BACKUP_COUNT = 3

class LogSignaler(QObject):
    log_signal = Signal(str, str)

class QtLogHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.signaler = LogSignaler()

    def emit(self, record):
        try:
            msg = self.format(record)
            try:
                self.signaler.log_signal.emit(record.levelname, msg)
            except RuntimeError:
                pass
        except Exception:
            self.handleError(record)

def setup_logger():
    if getattr(sys, 'frozen', False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    log_path = os.path.join(base_dir, LOG_DIR)
    os.makedirs(log_path, exist_ok=True)
    full_path = os.path.join(log_path, LOG_FILE)

    logger = logging.getLogger("SuperAgent")
    logger.setLevel(logging.INFO)
    logger.propagate = False 

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.CRITICAL) 
    
    # 🔴 APPLICA LA BLINDATURA GLOBALE
    if not any(isinstance(f, SecretFilter) for f in root_logger.filters):
        root_logger.addFilter(SecretFilter())
        
    if not any(isinstance(f, SecretFilter) for f in logger.filters):
        logger.addFilter(SecretFilter())
    
    if logger.hasHandlers():
        logger.handlers.clear()

    formatter = logging.Formatter('%(asctime)s | %(levelname)s | %(message)s', datefmt='%H:%M:%S')

    try:
        file_handler = RotatingFileHandler(full_path, maxBytes=MAX_BYTES, backupCount=BACKUP_COUNT, encoding='utf-8')
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except Exception as e:
        print(f"ERRORE CRITICO LOGGER: {e}")

    qt_handler = QtLogHandler()
    qt_handler.setFormatter(formatter)
    logger.addHandler(qt_handler)

    logger.info("=== 🚀 SISTEMA DI LOG V8.5 (SECURE EDITION) AVVIATO ===")
    return logger, qt_handler.signaler
