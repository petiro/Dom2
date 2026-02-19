import sys
import yaml
import os
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QPushButton, QTextEdit, 
                             QTabWidget, QLineEdit, QComboBox, QCheckBox, 
                             QGroupBox, QFormLayout, QListWidget, QMessageBox, QSplitter)
from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QFont

from core.config_paths import CONFIG_DIR

ROBOTS_FILE = os.path.join(CONFIG_DIR, "robots.yaml")

class RobotsTab(QWidget):
    def __init__(self, logger, controller):
        super().__init__()
        self.logger = logger
        self.controller = controller
        self.robots_data = []
        self.current_index = -1
        self.init_ui()
        self.load_robots()
        self.controller.ai_analysis_ready.connect(self.show_ai_response)

    def init_ui(self):
        layout = QHBoxLayout(self)

        # SINISTRA
        left_panel = QVBoxLayout()
        self.robot_list = QListWidget()
        self.robot_list.currentRowChanged.connect(self.select_robot)
        font = QFont(); font.setPointSize(11); self.robot_list.setFont(font)
        
        left_panel.addWidget(QLabel("📋 SELEZIONA ROBOT:"))
        left_panel.addWidget(self.robot_list)
        
        self.btn_add = QPushButton("➕ NUOVO ROBOT")
        self.btn_add.setStyleSheet("background-color: #2980b9; color: white;")
        self.btn_add.clicked.connect(self.add_robot)
        self.btn_save = QPushButton("💾 SALVA TUTTO")
        self.btn_save.setStyleSheet("background-color: #27ae60; color: white;")
        self.btn_save.clicked.connect(self.save_robots_to_disk)
        
        left_panel.addWidget(self.btn_add)
        left_panel.addWidget(self.btn_save)

        # DESTRA
        self.right_group = QGroupBox("⚙️ CONFIGURAZIONE STRATEGIA")
        self.right_layout = QVBoxLayout()

        ctrl_layout = QHBoxLayout()
        self.btn_toggle = QPushButton("⏸ PAUSA"); self.btn_toggle.clicked.connect(self.toggle_active)
        self.btn_delete = QPushButton("🗑 ELIMINA"); self.btn_delete.clicked.connect(self.delete_robot)
        ctrl_layout.addWidget(self.btn_toggle)
        ctrl_layout.addWidget(self.btn_delete)
        self.right_layout.addLayout(ctrl_layout)

        form_layout = QFormLayout()
        self.input_name = QLineEdit(); self.input_name.textChanged.connect(self.update_data)
        self.input_triggers = QLineEdit(); self.input_triggers.textChanged.connect(self.update_data)
        self.input_exclude = QLineEdit(); self.input_exclude.textChanged.connect(self.update_data)
        self.combo_mm = QComboBox(); self.combo_mm.addItems(["Fisso (€)", "Roserpina (Progressione)"]); self.combo_mm.currentIndexChanged.connect(self.update_data)
        self.input_stake = QLineEdit(); self.input_stake.textChanged.connect(self.update_data)
        self.input_chat_ids = QLineEdit(); self.input_chat_ids.setPlaceholderText("-1001, -1002"); self.input_chat_ids.textChanged.connect(self.update_data)

        form_layout.addRow("Nome:", self.input_name)
        form_layout.addRow("Trigger:", self.input_triggers)
        form_layout.addRow("Exclude:", self.input_exclude)
        form_layout.addRow("Money M.:", self.combo_mm)
        form_layout.addRow("Stake:", self.input_stake)
        form_layout.addRow("Chat ID:", self.input_chat_ids)
        self.right_layout.addLayout(form_layout)

        # SEZIONE AI
        ai_group = QGroupBox("🧠 AI STRATEGY ARCHITECT")
        ai_layout = QVBoxLayout()
        self.input_template = QTextEdit(); self.input_template.setMaximumHeight(60); self.input_template.textChanged.connect(self.update_data)
        self.input_logic = QTextEdit(); self.input_logic.setMaximumHeight(60); self.input_logic.textChanged.connect(self.update_data)
        
        btn_ai = QPushButton("🔮 INTERPRETA REGOLA")
        btn_ai.setStyleSheet("background-color: #8e44ad; color: white; font-weight: bold;")
        btn_ai.clicked.connect(self.request_ai)
        
        self.txt_ai_feedback = QTextEdit()
        self.txt_ai_feedback.setStyleSheet("background-color: #2c3e50; color: #f1c40f;")
        
        ai_layout.addWidget(QLabel("1. Esempio Messaggio Telegram:")); ai_layout.addWidget(self.input_template)
        ai_layout.addWidget(QLabel("2. Descrivi Regola:")); ai_layout.addWidget(self.input_logic)
        ai_layout.addWidget(btn_ai)
        ai_layout.addWidget(QLabel("3. Interpretazione (Modificabile):")); ai_layout.addWidget(self.txt_ai_feedback)
        
        ai_group.setLayout(ai_layout)
        self.right_layout.addWidget(ai_group)
        self.right_group.setLayout(self.right_layout)
        self.right_group.setEnabled(False)

        splitter = QSplitter(Qt.Horizontal)
        left_widget = QWidget(); left_widget.setLayout(left_panel)
        splitter.addWidget(left_widget)
        splitter.addWidget(self.right_group)
        splitter.setStretchFactor(1, 2)
        layout.addWidget(splitter)

    def load_robots(self):
        if os.path.exists(ROBOTS_FILE):
            with open(ROBOTS_FILE, 'r') as f: self.robots_data = yaml.safe_load(f) or []
        self.refresh_list()

    def refresh_list(self):
        self.robot_list.clear()
        for r in self.robots_data:
            s = "🟢" if r.get('enabled', True) else "⏸️"
            self.robot_list.addItem(f"{s} {r.get('name', 'Nuovo')}")

    def select_robot(self, idx):
        if idx < 0 or idx >= len(self.robots_data):
            self.right_group.setEnabled(False); return
        self.current_index = idx
        self.right_group.setEnabled(True)
        data = self.robots_data[idx]
        
        self.block(True)
        self.input_name.setText(data.get('name', ''))
        self.input_triggers.setText(", ".join(data.get('trigger_words', [])))
        self.input_exclude.setText(", ".join(data.get('exclude_words', [])))
        self.combo_mm.setCurrentText(data.get('mm_mode', "Fisso (€)"))
        self.input_stake.setText(str(data.get('stake_value', '')))
        
        chats = data.get('specific_chat_id', '')
        if isinstance(chats, list): self.input_chat_ids.setText(", ".join(map(str, chats)))
        else: self.input_chat_ids.setText(str(chats) if chats else "")

        self.input_template.setPlainText(data.get('msg_template', ''))
        self.input_logic.setPlainText(data.get('logic_description', ''))
        self.txt_ai_feedback.setPlainText(data.get('ai_interpretation', ''))
        self.block(False)

    def update_data(self):
        if self.current_index < 0: return
        data = self.robots_data[self.current_index]
        data['name'] = self.input_name.text()
        data['trigger_words'] = [w.strip() for w in self.input_triggers.text().split(',') if w.strip()]
        data['exclude_words'] = [w.strip() for w in self.input_exclude.text().split(',') if w.strip()]
        data['mm_mode'] = self.combo_mm.currentText()
        try: data['stake_value'] = float(self.input_stake.text())
        except: data['stake_value'] = 0.0
        data['specific_chat_id'] = self.input_chat_ids.text()
        data['msg_template'] = self.input_template.toPlainText()
        data['logic_description'] = self.input_logic.toPlainText()
        
        self.robot_list.item(self.current_index).setText(f"{'🟢' if data.get('enabled', True) else '⏸️'} {data['name']}")

    def toggle_active(self):
        if self.current_index < 0: return
        self.robots_data[self.current_index]['enabled'] = not self.robots_data[self.current_index].get('enabled', True)
        self.refresh_list(); self.robot_list.setCurrentRow(self.current_index)

    def request_ai(self):
        self.txt_ai_feedback.setPlainText("⏳ Analisi in corso...")
        self.controller.test_ai_strategy(self.input_logic.toPlainText(), self.input_template.toPlainText())

    @Slot(str)
    def show_ai_response(self, response):
        self.txt_ai_feedback.setPlainText(response)
        if self.current_index >= 0:
            self.robots_data[self.current_index]['ai_interpretation'] = response

    def block(self, b):
        self.input_name.blockSignals(b); self.input_triggers.blockSignals(b); self.input_exclude.blockSignals(b)
        self.combo_mm.blockSignals(b); self.input_stake.blockSignals(b); self.input_chat_ids.blockSignals(b)
        self.input_template.blockSignals(b); self.input_logic.blockSignals(b)

    def add_robot(self):
        self.robots_data.append({"name": "Nuovo Robot", "enabled": True})
        self.refresh_list(); self.robot_list.setCurrentRow(len(self.robots_data)-1)

    def delete_robot(self):
        if self.current_index >= 0:
            del self.robots_data[self.current_index]
            self.refresh_list(); self.select_robot(-1)

    def save_robots_to_disk(self):
        with open(ROBOTS_FILE, 'w') as f: yaml.dump(self.robots_data, f)
        QMessageBox.information(self, "OK", "✅ Salvato!")

class DesktopApp(QMainWindow):
    def __init__(self, logger, executor, config, monitor, controller):
        super().__init__()
        self.logger = logger
        self.controller = controller
        self.setWindowTitle("DOM2 V8.5 - AI STRATEGY CENTER")
        self.resize(1300, 850)
        
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)
        self.tabs = QTabWidget()
        
        self.dashboard_tab = QWidget(); self.setup_dash(self.dashboard_tab); self.tabs.addTab(self.dashboard_tab, "📊 Dashboard")
        self.robots_tab = RobotsTab(self.logger, self.controller); self.tabs.addTab(self.robots_tab, "🤖 ROBOT STRATEGY")
        
        self.logs_tab = QWidget(); l = QVBoxLayout(self.logs_tab)
        self.log_output = QTextEdit(); self.log_output.setReadOnly(True); l.addWidget(self.log_output)
        self.tabs.addTab(self.logs_tab, "📝 Logs")
        
        layout.addWidget(self.tabs)
        self.controller.log_message.connect(self.log_output.append)

    def setup_dash(self, tab):
        l = QVBoxLayout(tab)
        l.addWidget(QLabel("SYSTEM STATUS: RUNNING (Vedi Config.yaml per modalita Real/Safe)"))

def run_app(logger, executor, config, monitor, controller):
    app = QApplication.instance()
    window = DesktopApp(logger, executor, config, monitor, controller)
    window.show()
    return app.exec()
