import os
import json
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
    QPushButton, QTextEdit, QProgressBar, QGroupBox, QScrollArea
)
from PySide6.QtCore import Slot

class MappingTab(QWidget):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self.api_config_path = os.path.join("config", "api_config.json")
        
        # Collegamento segnali
        if self.controller:
            self.controller.mapping_ready.connect(self.on_mapping_ready)
            
        self.init_ui()
        self.load_api_key()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        
        # SCROLL AREA
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        
        content_widget = QWidget()
        layout = QVBoxLayout(content_widget)

        # --- SEZIONE API KEY ---
        gb_api = QGroupBox("🔑 Configurazione AI (OpenRouter)")
        hb_api = QHBoxLayout()
        self.inp_api_key = QLineEdit()
        self.inp_api_key.setEchoMode(QLineEdit.Password)
        self.inp_api_key.setPlaceholderText("sk-or-v1-...")
        btn_save_key = QPushButton("Salva Key")
        btn_save_key.clicked.connect(self.save_api_key)
        
        hb_api.addWidget(QLabel("API Key:"))
        hb_api.addWidget(self.inp_api_key)
        hb_api.addWidget(btn_save_key)
        gb_api.setLayout(hb_api)
        layout.addWidget(gb_api)

        # --- SEZIONE MAPPING ---
        layout.addWidget(QLabel("🔗 URL Sito Target:"))
        self.inp_url = QLineEdit()
        self.inp_url.setPlaceholderText("https://www.bet365.it")
        layout.addWidget(self.inp_url)

        self.btn_start = QPushButton("🚀 Avvia Auto-Mapping AI")
        self.btn_start.setMinimumHeight(40)
        self.btn_start.setStyleSheet("background-color: #FF9800; color: black; font-weight: bold;")
        self.btn_start.clicked.connect(self.start_mapping)
        layout.addWidget(self.btn_start)

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        layout.addWidget(QLabel("📋 Risultato (Selettori YAML):"))
        self.txt_result = QTextEdit()
        self.txt_result.setPlaceholderText("Qui appariranno i selettori generati dall'AI...")
        self.txt_result.setMinimumHeight(300)
        layout.addWidget(self.txt_result)

        btn_save_yaml = QPushButton("💾 Salva come Default")
        btn_save_yaml.clicked.connect(self.save_yaml)
        layout.addWidget(btn_save_yaml)

        # Chiudi Scroll
        layout.addStretch()
        scroll.setWidget(content_widget)
        main_layout.addWidget(scroll)

    def load_api_key(self):
        if os.path.exists(self.api_config_path):
            try:
                with open(self.api_config_path, "r") as f:
                    data = json.load(f)
                    self.inp_api_key.setText(data.get("openrouter_api_key", ""))
            except: pass

    def save_api_key(self):
        key = self.inp_api_key.text().strip()
        data = {"openrouter_api_key": key}
        os.makedirs("config", exist_ok=True)
        with open(self.api_config_path, "w") as f:
            json.dump(data, f, indent=4)
        
        # Aggiorna il vault del controller se presente
        if self.controller and self.controller.vault:
            self.controller.vault.encrypt_data(data)
            
        self.btn_start.setText("✅ Key Salvata!")

    def start_mapping(self):
        url = self.inp_url.text()
        if not url: return
        self.progress.setVisible(True)
        self.progress.setRange(0, 0) # Indeterminate
        self.btn_start.setEnabled(False)
        self.txt_result.clear()
        
        if self.controller:
            self.controller.request_auto_mapping(url)

    @Slot(str)
    def on_mapping_ready(self, yaml_code):
        self.progress.setVisible(False)
        self.btn_start.setEnabled(True)
        self.txt_result.setPlainText(yaml_code)

    def save_yaml(self):
        if self.controller:
            self.controller.save_selectors_yaml(self.txt_result.toPlainText())
