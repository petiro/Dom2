import os
from datetime import datetime
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, 
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
    QGroupBox, QLineEdit, QHBoxLayout
)
from PySide6.QtCore import Slot, Qt

# Import dinamico per evitare crash se il core ha problemi
try:
    from core.telegram_worker import TelegramWorker
except ImportError:
    TelegramWorker = None 

class TelegramTab(QWidget):
    def __init__(self, agent=None, controller=None):
        super().__init__()
        self.controller = controller
        self.worker = None
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # Pannello Controllo
        control_group = QGroupBox("Stato Connessione")
        control_layout = QHBoxLayout(control_group)
        
        self.status_label = QLabel("Status: Pronto")
        self.status_label.setStyleSheet("font-weight: bold; color: #8e8ea0;")
        
        self.btn_connect = QPushButton("Avvia Telegram")
        self.btn_connect.clicked.connect(self.toggle_worker)
        self.btn_connect.setStyleSheet("background-color: #10a37f; color: white; font-weight: bold; padding: 8px;")
        
        control_layout.addWidget(self.status_label)
        control_layout.addWidget(self.btn_connect)
        layout.addWidget(control_group)
        
        # Tabella Messaggi
        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["Ora", "Messaggio"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.setStyleSheet("background-color: #202123; color: white; gridline-color: #444;")
        layout.addWidget(self.table)

    def toggle_worker(self):
        if self.worker and self.worker.isRunning():
            self.stop_worker()
        else:
            self.start_worker()

    def start_worker(self):
        if TelegramWorker is None:
            QMessageBox.critical(self, "Errore", "Modulo core.telegram_worker non trovato.")
            return

        # Recupera config dal controller o usa valori vuoti per test
        if self.controller:
            config = self.controller.current_config.get('telegram', {})
            # Fallback se non è nel dizionario 'telegram' ma nella root
            if not config:
                config = self.controller.current_config
        else:
            config = {'api_id': 0, 'api_hash': ''} 

        self.worker = TelegramWorker(config)
        self.worker.status_changed.connect(self.update_status)
        self.worker.message_received.connect(self.add_message)
        self.worker.error_occurred.connect(self.handle_error)
        
        self.worker.start()
        self.btn_connect.setText("Arresta Telegram")
        self.btn_connect.setStyleSheet("background-color: #ef4444; color: white; font-weight: bold;")

    def stop_worker(self):
        if self.worker:
            self.update_status("Arresto in corso...")
            self.worker.stop()
            self.worker = None
        
        self.btn_connect.setText("Avvia Telegram")
        self.btn_connect.setStyleSheet("background-color: #10a37f; color: white; font-weight: bold;")
        self.update_status("Disconnesso")

    @Slot(str)
    def update_status(self, status):
        self.status_label.setText(f"Status: {status}")
        if "Connesso" in status:
            self.status_label.setStyleSheet("color: #22c55e; font-weight: bold;")
        elif "Errore" in status or "Richiesto" in status:
            self.status_label.setStyleSheet("color: #ef4444; font-weight: bold;")
        else:
            self.status_label.setStyleSheet("color: #8e8ea0; font-weight: bold;")

    @Slot(str)
    def add_message(self, text):
        row = self.table.rowCount()
        self.table.insertRow(row)
        
        ts = datetime.now().strftime("%H:%M:%S")
        item_ts = QTableWidgetItem(ts)
        item_ts.setTextAlignment(Qt.AlignCenter)
        item_msg = QTableWidgetItem(text)
        
        self.table.setItem(row, 0, item_ts)
        self.table.setItem(row, 1, item_msg)
        self.table.scrollToBottom()

    @Slot(str)
    def handle_error(self, err):
        self.update_status("Errore!")
        QMessageBox.critical(self, "Telegram Error", err)
        if "SESSION_MISSING" in err or "CONFIG ERROR" in err:
            self.stop_worker()
