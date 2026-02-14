import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from PySide6.QtCore import QObject, Signal

# Costanti
LOG_DIR = "logs"
LOG_FILE = "superagent.log"
MAX_BYTES = 5 * 1024 * 1024  # 5 MB
BACKUP_COUNT = 3

# --- 1. Classe Segnale Separata (Pattern Composizione) ---
# Evita conflitti di ereditarietà multipla con PySide6
class LogSignaler(QObject):
    log_signal = Signal(str, str)  # level, message

# --- 2. Handler Custom ---
class QtLogHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.signaler = LogSignaler()

    def emit(self, record):
        try:
            msg = self.format(record)
            # Emette il segnale tramite l'oggetto composito
            self.signaler.log_signal.emit(record.levelname, msg)
        except Exception:
            self.handleError(record)

def setup_logger():
    """Configura il logger e restituisce l'istanza logger e il segnalatore per la GUI"""
    
    # Calcolo Percorso Assoluto (Robusto per EXE e Script)
    if getattr(sys, 'frozen', False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    log_path = os.path.join(base_dir, LOG_DIR)
    os.makedirs(log_path, exist_ok=True)
    full_path = os.path.join(log_path, LOG_FILE)

    # Configurazione Logger "SuperAgent"
    logger = logging.getLogger("SuperAgent")
    logger.setLevel(logging.INFO)
    logger.propagate = False  # Evita duplicati
    
    # Pulisce handler precedenti per evitare log doppi al riavvio
    if logger.handlers:
        logger.handlers.clear()

    formatter = logging.Formatter(
        '%(asctime)s | %(levelname)s | %(message)s', 
        datefmt='%H:%M:%S'
    )

    # File Handler
    try:
        file_handler = RotatingFileHandler(
            full_path, 
            maxBytes=MAX_BYTES, 
            backupCount=BACKUP_COUNT, 
            encoding='utf-8'
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except Exception as e:
        print(f"ERRORE CRITICO LOGGER: Impossibile creare file di log: {e}")

    # Qt Handler
    qt_handler = QtLogHandler()
    qt_handler.setFormatter(formatter)
    logger.addHandler(qt_handler)

    # Test immediato di scrittura
    logger.info("=== 🚀 SISTEMA DI LOG AVVIATO ===")
    
    # Restituiamo il logger E il signaler (che contiene il segnale Qt)
    return logger, qt_handler.signaler
