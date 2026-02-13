import os
import yaml
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
    QPushButton, QListWidget, QMessageBox, QGroupBox, QScrollArea, QFormLayout
)
from PySide6.QtCore import Qt

class TelegramTab(QWidget):
    def __init__(self, controller=None):
        super().__init__()
        self.controller = controller
        self.config_path = os.path.join("config", "config.yaml")
        self.init_ui()
        self.load_config()

    def init_ui(self):
        # 1. Layout Principale con Scroll
        main_layout = QVBoxLayout(self)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        
        content_widget = QWidget()
        self.layout = QVBoxLayout(content_widget) # Layout interno
        
        # --- SEZIONE 1: CONFIGURAZIONE CREDENZIALI ---
        gb_config = QGroupBox("🔑 Credenziali Telegram (API)")
        form_layout = QFormLayout()
        
        self.inp_api_id = QLineEdit()
        self.inp_api_id.setPlaceholderText("Es: 1234567")
        
        self.inp_api_hash = QLineEdit()
        self.inp_api_hash.setPlaceholderText("Es: a1b2c3d4...")
        
        self.inp_phone = QLineEdit()
        self.inp_phone.setPlaceholderText("Es: +393331234567")
        
        btn_save_creds = QPushButton("💾 Salva e Connetti")
        btn_save_creds.setStyleSheet("background-color: #2196F3; color: white; font-weight: bold;")
        btn_save_creds.clicked.connect(self.save_and_connect)
        
        form_layout.addRow("API ID:", self.inp_api_id)
        form_layout.addRow("API HASH:", self.inp_api_hash)
        form_layout.addRow("Telefono:", self.inp_phone)
        form_layout.addRow(btn_save_creds)
        
        gb_config.setLayout(form_layout)
        self.layout.addWidget(gb_config)

        # --- SEZIONE 2: LISTA CANALI ---
        self.layout.addWidget(QLabel("📡 Canali Disponibili"))
        self.channel_list = QListWidget()
        self.channel_list.setSelectionMode(QListWidget.MultiSelection)
        self.layout.addWidget(self.channel_list)

        # --- SEZIONE 3: AZIONI ---
        btn_scan = QPushButton("🔄 Scansiona Canali")
        btn_scan.clicked.connect(self.scan_channels)
        self.layout.addWidget(btn_scan)

        btn_save_sel = QPushButton("✅ Salva Selezione Canali")
        btn_save_sel.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        btn_save_sel.clicked.connect(self.save_selection)
        self.layout.addWidget(btn_save_sel)

        # Chiudi Scroll
        self.layout.addStretch()
        scroll.setWidget(content_widget)
        main_layout.addWidget(scroll)

    def load_config(self):
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r") as f:
                    data = yaml.safe_load(f) or {}
                    tg = data.get("telegram", {})
                    self.inp_api_id.setText(str(tg.get("api_id", "")))
                    self.inp_api_hash.setText(str(tg.get("api_hash", "")))
                    self.inp_phone.setText(str(tg.get("phone", "")))
            except Exception as e:
                print(f"Errore load config: {e}")

    def save_and_connect(self):
        try:
            # Carica esistente
            current_conf = {}
            if os.path.exists(self.config_path):
                with open(self.config_path, "r") as f:
                    current_conf = yaml.safe_load(f) or {}

            # Aggiorna sezione telegram
            if "telegram" not in current_conf:
                current_conf["telegram"] = {}
            
            current_conf["telegram"]["api_id"] = self.inp_api_id.text()
            current_conf["telegram"]["api_hash"] = self.inp_api_hash.text()
            current_conf["telegram"]["phone"] = self.inp_phone.text()

            # Salva su file
            with open(self.config_path, "w") as f:
                yaml.dump(current_conf, f)

            QMessageBox.information(self, "Salvato", "Credenziali salvate!\nRiavvia l'app per connetterti.")
            
            # Se il controller è attivo, prova a riconnettere al volo
            if self.controller:
                self.controller.connect_telegram(current_conf["telegram"])

        except Exception as e:
            QMessageBox.critical(self, "Errore", f"Impossibile salvare: {e}")

    def scan_channels(self):
        # Qui chiameremmo il client telegram reale per ottenere i dialogs
        QMessageBox.information(self, "Info", "Scansione avviata in background (Log)...")
        # Mock per UI
        self.channel_list.addItems(["Canale Test 1", "Betting Gold", "Segnali VIP"])

    def save_selection(self):
        selected = [item.text() for item in self.channel_list.selectedItems()]
        QMessageBox.information(self, "Salvataggio", f"Canali monitorati: {len(selected)}")
