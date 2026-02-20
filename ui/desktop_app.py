import sys
import os
from pathlib import Path
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QLabel, QTextEdit, QTabWidget, QLineEdit, QFormLayout, 
                             QPushButton, QMessageBox)

# 🔴 IMPORTA I MODULI UI DEL VAULT SICURO
from ui.bookmaker_tab import BookmakerTab
from ui.selectors_tab import SelectorsTab
from ui.robots_tab import RobotsTab

class CloudApiTab(QWidget):
    def __init__(self, config):
        super().__init__()
        self.config = config
        self.save_dir = os.path.join(str(Path.home()), ".superagent_data")
        os.makedirs(self.save_dir, exist_ok=True)
        
        self.session_file = os.path.join(self.save_dir, "telegram_session.dat")
        self.openrouter_file = os.path.join(self.save_dir, "openrouter_key.dat")

        layout = QVBoxLayout()
        form_layout = QFormLayout()
        
        self.api_id_input = QLineEdit(str(config.get("telegram", {}).get("api_id", "")))
        self.api_hash_input = QLineEdit(config.get("telegram", {}).get("api_hash", ""))
        
        self.session_string_input = QLineEdit()
        self.session_string_input.setEchoMode(QLineEdit.Password)
        if os.path.exists(self.session_file):
            with open(self.session_file, "r", encoding="utf-8") as f: 
                self.session_string_input.setText(f.read().strip())

        self.openrouter_input = QLineEdit()
        self.openrouter_input.setEchoMode(QLineEdit.Password)
        if os.path.exists(self.openrouter_file):
            with open(self.openrouter_file, "r", encoding="utf-8") as f: 
                self.openrouter_input.setText(f.read().strip())

        form_layout.addRow(QLabel("<b>📱 TELEGRAM CLOUD</b>"))
        form_layout.addRow("API ID:", self.api_id_input)
        form_layout.addRow("API Hash:", self.api_hash_input)
        form_layout.addRow("🔑 Session String:", self.session_string_input)
        
        form_layout.addRow(QLabel("<br><b>🧠 AI / OPENROUTER</b>"))
        form_layout.addRow("🔑 API Key:", self.openrouter_input)
        
        layout.addLayout(form_layout)

        save_btn = QPushButton("💾 Salva Chiavi API & Cloud")
        save_btn.setStyleSheet("background-color: #8e44ad; color: white; font-weight: bold; padding: 8px;")
        save_btn.clicked.connect(self._save_settings)
        layout.addWidget(save_btn)
        layout.addStretch()
        self.setLayout(layout)

    def _save_settings(self):
        if "telegram" not in self.config: self.config["telegram"] = {}
        self.config["telegram"]["api_id"] = self.api_id_input.text().strip()
        self.config["telegram"]["api_hash"] = self.api_hash_input.text().strip()
        
        config_loader = __import__('core.config_loader').config_loader.ConfigLoader()
        config_loader.save_config(self.config)
        
        s_str = self.session_string_input.text().strip()
        if s_str: 
            with open(self.session_file, "w", encoding="utf-8") as f: f.write(s_str)
        elif os.path.exists(self.session_file): os.remove(self.session_file)

        or_key = self.openrouter_input.text().strip()
        if or_key: 
            with open(self.openrouter_file, "w", encoding="utf-8") as f: f.write(or_key)
        elif os.path.exists(self.openrouter_file): os.remove(self.openrouter_file)

        QMessageBox.information(self, "Successo", "Chiavi sicure salvate nel Vault Locale.")

class DesktopApp(QMainWindow):
    def __init__(self, logger, executor, config, monitor, controller):
        super().__init__()
        self.logger = logger
        self.controller = controller
        self.config = config
        self.setWindowTitle("SUPERAGENT OS - HEDGE GRADE 24/7")
        self.resize(1300, 850)
        
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)
        self.tabs = QTabWidget()
        
        self.dashboard_tab = QWidget()
        l = QVBoxLayout(self.dashboard_tab)
        l.addWidget(QLabel("<h2>SYSTEM STATUS: 🟢 WATCHDOG OS ACTIVE</h2><p>Tutti i dati sono protetti in ~/.superagent_data/. Backup automatico attivo.</p>"))
        l.addStretch()
        self.tabs.addTab(self.dashboard_tab, "📊 Dashboard")
        
        # 🔴 LE TRE TAB MODULARI CHE LEGGONO DAL VAULT
        self.tabs.addTab(BookmakerTab(), "💰 Bookmakers")
        self.tabs.addTab(SelectorsTab(), "🧩 Selettori")
        self.tabs.addTab(RobotsTab(self.logger, self.controller), "🤖 Robot & Strategie")
        
        # Cloud & AI
        self.cloud_tab = CloudApiTab(self.config)
        self.tabs.addTab(self.cloud_tab, "☁️ Cloud & API")
        
        # Logs
        self.logs_tab = QWidget(); log_l = QVBoxLayout(self.logs_tab)
        self.log_output = QTextEdit(); self.log_output.setReadOnly(True)
        self.log_output.setStyleSheet("background-color: #1e1e1e; color: #00ff00; font-family: monospace;")
        log_l.addWidget(self.log_output)
        self.tabs.addTab(self.logs_tab, "📝 Logs")
        
        layout.addWidget(self.tabs)
        self.controller.log_message.connect(self.log_output.append)

def run_app(logger, executor, config, monitor, controller):
    app = QApplication.instance()
    window = DesktopApp(logger, executor, config, monitor, controller)
    window.show()
    return app.exec()
