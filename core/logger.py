import logging
import os
from logging.handlers import RotatingFileHandler
from PySide6.QtCore import QObject, Signal

# Costanti
LOG_DIR = "logs"
LOG_FILE = "superagent.log"
MAX_BYTES = 5 * 1024 * 1024  # 5 MB per file
BACKUP_COUNT = 3 

class QtLogHandler(logging.Handler, QObject):
    """Intercetta i log ed emette un segnale Qt per la UI thread-safe"""
    log_signal = Signal(str, str) # level, message

    def __init__(self):
        logging.Handler.__init__(self)
        QObject.__init__(self)

    def emit(self, record):
        try:
            msg = self.format(record)
            self.log_signal.emit(record.levelname, msg)
        except Exception:
            self.handleError(record)

def setup_logger():
    """Configura logger su file e per la GUI"""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    log_path = os.path.join(base_dir, LOG_DIR)
    os.makedirs(log_path, exist_ok=True)
    full_path = os.path.join(log_path, LOG_FILE)

    logger = logging.getLogger("SuperAgent")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    
    if logger.handlers: logger.handlers.clear()

    formatter = logging.Formatter('%(asctime)s | %(levelname)s | %(message)s', datefmt='%H:%M:%S')

    # File Handler
    file_handler = RotatingFileHandler(full_path, maxBytes=MAX_BYTES, backupCount=BACKUP_COUNT, encoding='utf-8')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Qt Handler (per la finestra)
    qt_handler = QtLogHandler()
    qt_handler.setFormatter(formatter)
    logger.addHandler(qt_handler)

    return logger, qt_handler
