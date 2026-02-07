"""
SuperAgent Desktop UI - Modern Interface (Singleton & Immortality Edition)
Sincronizzato con l'architettura Singleton Executor e HealthMonitor.
"""
import sys
import os
import json
import yaml
import time
from datetime import datetime
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QTextEdit, QPushButton, QLabel, QLineEdit,
    QTableWidget, QTableWidgetItem, QSplitter, QStatusBar,
    QGroupBox, QCheckBox, QSpinBox, QProgressBar, QMessageBox,
    QComboBox
)
from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtGui import QFont, QColor, QPalette

from ui.telegram_tab import TelegramTab

# PATCH: Importiamo il battito cardiaco globale dal main se necessario, 
# o gestiamo un segnale per il monitor.
import main 

class RPAWorker(QThread):
    """
    Worker per l'automazione browser.
    Usa l'executor SINGLETON passato dal main, evitando conflitti di profilo.
    """
    log_signal = Signal(str)
    status_signal = Signal(str)
    finished = Signal()

    def __init__(self, executor, logger, rpa_healer=None, task_data=None):
        super().__init__()
        self.executor = executor  # Ricevuto dal Singleton del Main
        self.logger = logger
        self.healer = rpa_healer
        self.task_data = task_data
        self.running = True

    def run(self):
        try:
            self.log_signal.emit("🤖 RPA Worker avviato utilizzando Singleton Executor...")
            
            # Segnala al monitor che il thread è partito
            main.last_heartbeat = time.time()

            if not self.executor:
                self.log_signal.emit("❌ Errore: Executor non inizializzato.")
                return

            # Esempio di workflow RPA usando l'executor condiviso
            if self.task_data:
                teams = self.task_data.get('teams')
                self.log_signal.emit(f"Navigazione verso il match: {teams}")
                
                # Qui usiamo i metodi 'Ghost/Stealth' dell'executor
                success = self.executor.navigate_to_match(teams, {})
                
                # Aggiorna heartbeat durante operazioni lunghe
                main.last_heartbeat = time.time()

                if success:
                    self.log_signal.emit("✅ Match trovato. In attesa di segnali operativi...")
                else:
                    self.log_signal.emit("⚠️ Match non trovato o errore caricamento.")

        except Exception as e:
            self.log_signal.emit(f"❌ Errore RPA: {str(e)}")
        finally:
            self.finished.emit()

class MainWindow(QMainWindow):
    def __init__(self, vision_learner=None, telegram_learner=None, 
                 rpa_healer=None, logger=None, executor=None):
        super().__init__()
        self.setWindowTitle("SuperAgent Pro - H24 Immortal Edition")
        self.resize(1200, 800)
        self.start_time = datetime.now()
        
        # Iniezione Dipendenze (Singleton)
        self.vision = vision_learner
        self.telegram_learner = telegram_learner
        self.rpa_healer = rpa_healer
        self.logger = logger
        self.executor = executor # Il browser unico

        self.setup_ui()
        
        # Timer per l'Heartbeat della UI (ogni 30 secondi)
        self.heartbeat_timer = QTimer()
        self.heartbeat_timer.timeout.connect(self.send_heartbeat)
        self.heartbeat_timer.start(30000)

    def send_heartbeat(self):
        """Aggiorna il timestamp nel main per evitare il freeze-restart."""
        main.last_heartbeat = time.time()
        self.update_status()

    def setup_ui(self):
        # ... (Layout dei Tab rimane simile al tuo originale) ...
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        # Inizializza i Tab passandogli le dipendenze
        self.telegram_tab = TelegramTab(self.telegram_learner, self.logger)
        self.tabs.addTab(self.telegram_tab, "Monitor Telegram")
        
        # Aggiungi qui gli altri Tab (Chat, RPA, Settings...)
        # ...

        # Status Bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.apply_theme()

    def apply_theme(self):
        """Tema Dark Professionale."""
        palette = QPalette()
        palette.setColor(QPalette.Window, QColor(45, 45, 45))
        palette.setColor(QPalette.WindowText, Qt.white)
        palette.setColor(QPalette.Base, QColor(30, 30, 30))
        # ... (resto del tuo schema colori) ...
        self.setPalette(palette)

    def update_status(self):
        uptime = datetime.now() - self.start_time
        self.status_bar.showMessage(f"Uptime: {int(uptime.total_seconds())}s | Browser: {'Attivo' if self.executor else 'Offline'}")

def run_app(vision_learner=None, telegram_learner=None, 
            rpa_healer=None, logger=None, executor=None):
    """Entry point per l'applicazione desktop."""
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    window = MainWindow(vision_learner, telegram_learner, rpa_healer, logger, executor)
    window.show()
    
    return app.exec()
