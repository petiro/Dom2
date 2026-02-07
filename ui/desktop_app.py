"""
SuperAgent Desktop UI - Modern Interface (Singleton Ready)
"""
import sys
import os
import time
from datetime import datetime
from PySide6.QtWidgets import QApplication, QMainWindow, QTabWidget, QStatusBar
from PySide6.QtCore import Qt, QTimer
from ui.telegram_tab import TelegramTab

class MainWindow(QMainWindow):
    # AGGIORNATO: Il costruttore ora accetta 'executor'
    def __init__(self, vision_learner=None, telegram_learner=None, rpa_healer=None, logger=None, executor=None):
        super().__init__()
        self.setWindowTitle("SuperAgent Pro - H24 Immortal")
        self.resize(1200, 800)
        self.start_time = datetime.now()
        
        # ASSEGNAZIONE SINGLETON
        self.vision = vision_learner
        self.telegram_learner = telegram_learner
        self.rpa_healer = rpa_healer
        self.logger = logger
        self.executor = executor  # Usa l'istanza creata nel main.py

        self.setup_ui()
        
        # Timer per aggiornare lo stato e l'uptime
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_status)
        self.timer.start(1000)

    def setup_ui(self):
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        # Inizializza i Tab passandogli l'executor se necessario
        self.telegram_tab = TelegramTab(self.telegram_learner, self.logger)
        self.tabs.addTab(self.telegram_tab, "Monitor Telegram")
        
        # Altri tab...
        
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

    def update_status(self):
        uptime = datetime.now() - self.start_time
        # Visualizza se il browser è collegato
        browser_status = "ONLINE" if self.executor and self.executor.page else "OFFLINE"
        self.status_bar.showMessage(f"Uptime: {int(uptime.total_seconds())}s | Browser: {browser_status}")

# AGGIORNATO: La firma ora accetta executor
def run_app(vision_learner=None, telegram_learner=None, rpa_healer=None, logger=None, executor=None):
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    # Passiamo l'executor alla MainWindow
    window = MainWindow(vision_learner, telegram_learner, rpa_healer, logger, executor)
    window.show()

    return app.exec()