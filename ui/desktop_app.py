"""
SuperAgent Desktop App V6.0 - Stable Edition
- Vault criptato per le chiavi API (AES-256)
- Percorsi assoluti ovunque
- Codice morto eliminato (mapping_tab, telegram_tab integrati)
"""
import os
import sys
import json
import logging
from datetime import datetime

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QPushButton, QLabel, QLineEdit, QGroupBox, QTabWidget,
    QTableWidget, QTableWidgetItem, QMessageBox, QComboBox, QFormLayout,
    QListWidget, QFrame, QScrollArea, QHeaderView, QRadioButton, QButtonGroup,
    QDoubleSpinBox, QSpinBox, QCheckBox, QSizePolicy
)
from PySide6.QtCore import Qt, Signal, QTimer, Slot, QObject, QEvent
from PySide6.QtGui import QColor, QPalette, QFont

from core.utils import get_project_root
from core.security import Vault

_ROOT_DIR = get_project_root()
ROBOTS_FILE = os.path.join(_ROOT_DIR, "config", "my_robots.json")

# --- STYLESHEET ---
STYLE_SHEET = """
QMainWindow, QWidget { background-color: #1e1e1e; color: #e0e0e0; font-family: 'Segoe UI', sans-serif; }
QTabWidget::pane { border: 1px solid #333; }
QTabBar::tab { background: #2d2d2d; color: #888; padding: 10px 20px; border-radius: 4px; margin-right: 2px; }
QTabBar::tab:selected { background: #3e3e3e; color: #4caf50; border-bottom: 2px solid #4caf50; font-weight: bold; }
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QTextEdit { background-color: #333; color: white; border: 1px solid #444; border-radius: 4px; padding: 6px; }
QLineEdit:focus, QSpinBox:focus { border: 1px solid #4caf50; }
QPushButton { background-color: #3a3a3a; color: white; border: 1px solid #555; padding: 8px 15px; border-radius: 4px; }
QPushButton:hover { background-color: #444; border-color: #4caf50; }
QGroupBox { border: 1px solid #444; border-radius: 6px; margin-top: 20px; font-weight: bold; }
QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; color: #4caf50; }
QHeaderView::section { background-color: #2d2d2d; padding: 4px; border: 1px solid #333; }
QTableWidget { gridline-color: #333; }
QScrollArea { border: none; background-color: transparent; }
QScrollArea > QWidget > QWidget { background-color: transparent; }
QScrollBar:vertical { border: none; background: #2d2d2d; width: 10px; margin: 0px; }
QScrollBar::handle:vertical { background: #555; min-height: 20px; border-radius: 5px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
"""


# ============================================================================
#  HELPER: SCROLL WRAPPER
# ============================================================================
def create_scroll_layout(parent_widget):
    outer_layout = QVBoxLayout(parent_widget)
    outer_layout.setContentsMargins(0, 0, 0, 0)
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.NoFrame)
    content_widget = QWidget()
    content_layout = QVBoxLayout(content_widget)
    scroll.setWidget(content_widget)
    outer_layout.addWidget(scroll)
    return content_layout


# ============================================================================
#  1. SUPERVISOR TAB
# ============================================================================
class SupervisorTab(QWidget):
    def __init__(self, controller, factory):
        super().__init__()
        self.controller = controller
        self.factory = factory
        self.init_ui()

    def init_ui(self):
        layout = create_scroll_layout(self)

        header = QFrame()
        header.setStyleSheet("background-color: #252526; padding: 10px; border-radius: 5px;")
        h_lay = QHBoxLayout(header)

        lbl_stat = QLabel("🛡️ SUPERVISOR SYSTEM V6.0")
        lbl_stat.setStyleSheet("font-weight: bold; font-size: 14px; color: #4CAF50;")

        self.mode_group = QButtonGroup(self)
        self.rb_demo = QRadioButton("🛡️ DEMO (Safe)")
        self.rb_live = QRadioButton("💸 LIVE (Soldi Veri)")
        self.rb_demo.setChecked(True)
        self.rb_demo.setStyleSheet("color: #4CAF50; font-weight: bold;")
        self.rb_live.setStyleSheet("color: #F44336; font-weight: bold;")

        self.mode_group.addButton(self.rb_demo)
        self.mode_group.addButton(self.rb_live)
        self.mode_group.buttonToggled.connect(self.on_mode_changed)

        h_lay.addWidget(lbl_stat)
        h_lay.addStretch()
        h_lay.addWidget(QLabel("Modalita:"))
        h_lay.addWidget(self.rb_demo)
        h_lay.addWidget(self.rb_live)
        h_lay.addStretch()

        btn_kill = QPushButton("☢️ EMERGENCY STOP")
        btn_kill.setMinimumHeight(40)
        btn_kill.setStyleSheet("QPushButton { background-color: #B71C1C; color: white; font-weight: bold; }")
        btn_kill.clicked.connect(self.kill_system)
        h_lay.addWidget(btn_kill)

        layout.addWidget(header)

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setMinimumHeight(300)
        self.log.setStyleSheet("background-color: #000; color: #0f0; font-family: 'Consolas'; font-size: 11px;")
        layout.addWidget(self.log)

    def on_mode_changed(self, btn, checked):
        if checked:
            is_live = (btn == self.rb_live)
            if self.controller:
                self.controller.set_live_mode(is_live)
                if is_live:
                    self.log.append("<span style='color:red'>⚠️ ATTENZIONE: MODALITA LIVE ATTIVATA.</span>")
                else:
                    self.log.append("<span style='color:green'>🛡️ MODALITA DEMO ATTIVATA.</span>")

    def kill_system(self):
        if QMessageBox.question(self, "STOP", "SEI SICURO? Questo arrestera tutto.",
                                QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            self.log.append("🚨 EMERGENCY STOP ACTIVATED")
            if self.controller:
                self.controller.shutdown()
            if self.factory:
                for name in self.factory.robots_data:
                    self.factory.robots_data[name]["active"] = False
                self.factory.save_data()


# ============================================================================
#  2. MONEY TAB (Roserpina)
# ============================================================================
class MoneyTab(QWidget):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self.init_ui()
        self.load_config()

    def init_ui(self):
        layout = create_scroll_layout(self)

        lbl_title = QLabel("💰 GESTIONE CAPITALE (ROSERPINA)")
        lbl_title.setStyleSheet("font-size: 18px; font-weight: bold; color: #FFD700;")
        layout.addWidget(lbl_title)

        self.cmb_mode = QComboBox()
        self.cmb_mode.addItems(["Stake Fisso", "Roserpina"])
        self.cmb_mode.currentTextChanged.connect(self.toggle_inputs)
        layout.addWidget(QLabel("Strategia:"))
        layout.addWidget(self.cmb_mode)

        group_params = QGroupBox("Parametri")
        form_params = QFormLayout(group_params)

        self.sb_bankroll = QDoubleSpinBox()
        self.sb_bankroll.setRange(10, 100000)
        self.sb_bankroll.setValue(100.0)
        self.sb_bankroll.setPrefix("€ ")
        self.sb_bankroll.setStyleSheet("font-weight: bold; font-size: 14px; color: #FFF;")

        self.sb_target_pct = QDoubleSpinBox()
        self.sb_target_pct.setRange(0.1, 500)
        self.sb_target_pct.setValue(1.0)
        self.lbl_target = QLabel("Target/Importo:")

        self.sb_wins_needed = QSpinBox()
        self.sb_wins_needed.setRange(1, 20)
        self.sb_wins_needed.setValue(3)
        self.lbl_wins = QLabel("Prese da fare:")

        form_params.addRow("🏦 Budget Iniziale:", self.sb_bankroll)
        form_params.addRow(self.lbl_target, self.sb_target_pct)
        form_params.addRow(self.lbl_wins, self.sb_wins_needed)
        layout.addWidget(group_params)

        self.lbl_info = QLabel("")
        self.lbl_info.setWordWrap(True)
        self.lbl_info.setStyleSheet("color: #aaa; margin: 10px; font-style: italic;")
        layout.addWidget(self.lbl_info)

        btn_save = QPushButton("💾 SALVA CONFIGURAZIONE")
        btn_save.setStyleSheet("background-color: #2196F3; font-weight: bold; padding: 10px;")
        btn_save.clicked.connect(self.save_config)
        layout.addWidget(btn_save)

        btn_reset = QPushButton("♻️ RESET CICLO")
        btn_reset.setStyleSheet("background-color: #555; margin-top: 5px;")
        btn_reset.clicked.connect(self.reset_cycle_data)
        layout.addWidget(btn_reset)

        layout.addStretch()

    def toggle_inputs(self, text):
        if text == "Roserpina":
            self.lbl_target.setText("Resa Obiettivo (%):")
            self.sb_target_pct.setSuffix("%")
            self.sb_target_pct.setValue(45.0)
            self.sb_wins_needed.setVisible(True)
            self.lbl_wins.setVisible(True)
            self.lbl_info.setText("Roserpina: Calcola lo stake per ottenere la % di resa.")
        else:
            self.lbl_target.setText("Importo Fisso:")
            self.sb_target_pct.setSuffix(" €")
            self.sb_target_pct.setValue(1.0)
            self.sb_wins_needed.setVisible(False)
            self.lbl_wins.setVisible(False)
            self.lbl_info.setText("Stake Fisso: Punta sempre lo stesso importo.")

    def save_config(self):
        data = {
            "strategy": self.cmb_mode.currentText(),
            "bankroll": self.sb_bankroll.value(),
            "target_pct": self.sb_target_pct.value(),
            "wins_needed": self.sb_wins_needed.value(),
            "fixed_amount": self.sb_target_pct.value()
        }
        try:
            config_dir = os.path.join(_ROOT_DIR, "config")
            os.makedirs(config_dir, exist_ok=True)
            with open(os.path.join(config_dir, "money_config.json"), "w") as f:
                json.dump(data, f, indent=4)
            if self.controller:
                self.controller.reload_money_manager()
            QMessageBox.information(self, "Salvato", "Configurazione Aggiornata!")
        except Exception as e:
            QMessageBox.critical(self, "Errore", f"Impossibile salvare: {e}")

    def reset_cycle_data(self):
        if QMessageBox.question(self, "Reset", "Resettare il ciclo?",
                                QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            try:
                path = os.path.join(_ROOT_DIR, "config", "roserpina_real_state.json")
                if os.path.exists(path):
                    os.remove(path)
                if self.controller:
                    self.controller.reload_money_manager()
            except Exception as e:
                logging.getLogger("SuperAgent").error(f"Errore reset ciclo: {e}")

    def load_config(self):
        path = os.path.join(_ROOT_DIR, "config", "money_config.json")
        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    data = json.load(f)
                    self.sb_bankroll.setValue(float(data.get("bankroll", 100.0)))
                    strat = data.get("strategy", "Stake Fisso")
                    self.cmb_mode.setCurrentText(strat)
                    self.toggle_inputs(strat)
                    if strat == "Roserpina":
                        self.sb_target_pct.setValue(float(data.get("target_pct", 45.0)))
                    else:
                        self.sb_target_pct.setValue(float(data.get("fixed_amount", 1.0)))
                    self.sb_wins_needed.setValue(int(data.get("wins_needed", 3)))
            except Exception as e:
                logging.getLogger("SuperAgent").error(f"Errore load config money: {e}")


# ============================================================================
#  3. FACTORY TAB (Agenti & Chat)
# ============================================================================
class RobotFactoryTab(QWidget):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self.robots_data = {}
        self.current_robot_name = None
        self.init_ui()
        self.load_data()

    def init_ui(self):
        main_layout = create_scroll_layout(self)
        h_container = QWidget()
        layout = QHBoxLayout(h_container)
        main_layout.addWidget(h_container)

        # SX
        left_panel = QFrame()
        left_panel.setFixedWidth(250)
        left_panel.setStyleSheet("background-color: #252526; border-radius: 5px;")
        left_layout = QVBoxLayout(left_panel)
        left_layout.addWidget(QLabel("🤖 AGENTI ATTIVI"))
        self.robot_list = QListWidget()
        self.robot_list.setStyleSheet("background-color: #333; border: none;")
        self.robot_list.currentItemChanged.connect(self.on_robot_select)
        left_layout.addWidget(self.robot_list)
        btn_add = QPushButton("+ NUOVO AGENTE")
        btn_add.setStyleSheet("background-color: #2E7D32; color: white;")
        btn_add.clicked.connect(self.new_robot)
        left_layout.addWidget(btn_add)
        btn_del = QPushButton("🗑 ELIMINA")
        btn_del.setStyleSheet("background-color: #B71C1C; color: white;")
        btn_del.clicked.connect(self.delete_robot)
        left_layout.addWidget(btn_del)
        layout.addWidget(left_panel)

        # DX
        self.right_panel = QTabWidget()
        self.right_panel.setStyleSheet("QTabWidget::pane { border: 1px solid #444; }")

        self.tab_chat = QWidget()
        chat_layout = QVBoxLayout(self.tab_chat)
        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        self.chat_display.setStyleSheet("background-color: #1e1e1e; color: #00E676; font-family: Consolas;")
        self.chat_input = QLineEdit()
        self.chat_input.setPlaceholderText("Parla con questo robot...")
        self.chat_input.returnPressed.connect(self.send_to_robot)
        btn_send_chat = QPushButton("INVIA AL CERVELLO 🧠")
        btn_send_chat.clicked.connect(self.send_to_robot)
        chat_layout.addWidget(self.chat_display)
        chat_layout.addWidget(self.chat_input)
        chat_layout.addWidget(btn_send_chat)

        self.tab_config = QWidget()
        conf_layout = QFormLayout(self.tab_config)
        self.inp_name = QLineEdit()
        self.chk_active = QCheckBox("Agente Attivo")
        self.inp_telegram_filter = QLineEdit()
        self.inp_telegram_filter.setPlaceholderText("Es: 'Serie A', 'Live'")
        conf_layout.addRow("Nome Agente:", self.inp_name)
        conf_layout.addRow("Stato:", self.chk_active)
        conf_layout.addRow("Filtro Telegram:", self.inp_telegram_filter)
        btn_save = QPushButton("💾 SALVA")
        btn_save.clicked.connect(self.save_current)
        conf_layout.addWidget(btn_save)

        self.tab_site = QWidget()
        site_layout = QVBoxLayout(self.tab_site)
        self.txt_selectors = QTextEdit()
        site_layout.addWidget(QLabel("Mappatura Sito (JSON/YAML):"))
        site_layout.addWidget(self.txt_selectors)

        self.right_panel.addTab(self.tab_chat, "💬 Memoria & Chat")
        self.right_panel.addTab(self.tab_config, "⚙️ Config & Telegram")
        self.right_panel.addTab(self.tab_site, "🌐 Sito & Selettori")

        layout.addWidget(self.right_panel)
        self.right_panel.setVisible(False)

    def load_data(self):
        if os.path.exists(ROBOTS_FILE):
            try:
                with open(ROBOTS_FILE, 'r') as f:
                    self.robots_data = json.load(f)
                self.refresh_list()
            except Exception:
                pass

    def save_data(self):
        try:
            os.makedirs(os.path.dirname(ROBOTS_FILE), exist_ok=True)
            with open(ROBOTS_FILE, 'w') as f:
                json.dump(self.robots_data, f, indent=4)
        except Exception:
            pass

    def refresh_list(self):
        self.robot_list.clear()
        for name in self.robots_data:
            self.robot_list.addItem(name)

    def on_robot_select(self, current, previous):
        if not current:
            self.right_panel.setVisible(False)
            return
        self.right_panel.setVisible(True)
        self.current_robot_name = current.text()
        data = self.robots_data.get(self.current_robot_name, {})

        self.inp_name.setText(self.current_robot_name)
        self.chk_active.setChecked(data.get("active", True))
        self.inp_telegram_filter.setText(data.get("telegram_filter", ""))
        self.txt_selectors.setText(json.dumps(data.get("selectors", {}), indent=2))

        self.chat_display.clear()
        for msg in data.get("chat_history", []):
            role = "👤 TU" if msg['role'] == 'user' else "🤖 AGENTE"
            color = "#FFFFFF" if msg['role'] == 'user' else "#00E676"
            self.chat_display.append(f"<b style='color:{color}'>{role}:</b> {msg['content']}<br>")

    def new_robot(self):
        name = f"Agente_{len(self.robots_data) + 1}"
        self.robots_data[name] = {"active": False, "telegram_filter": "", "chat_history": [], "selectors": {}}
        self.save_data()
        self.refresh_list()

    def delete_robot(self):
        if self.robot_list.currentItem():
            del self.robots_data[self.robot_list.currentItem().text()]
            self.save_data()
            self.refresh_list()
            self.right_panel.setVisible(False)

    def save_current(self):
        if not self.current_robot_name:
            return
        new_name = self.inp_name.text().strip()
        if new_name != self.current_robot_name:
            self.robots_data[new_name] = self.robots_data.pop(self.current_robot_name)
            self.current_robot_name = new_name
            self.refresh_list()

        self.robots_data[new_name]["active"] = self.chk_active.isChecked()
        self.robots_data[new_name]["telegram_filter"] = self.inp_telegram_filter.text()
        try:
            self.robots_data[new_name]["selectors"] = json.loads(self.txt_selectors.toPlainText())
        except Exception:
            pass
        self.save_data()
        QMessageBox.information(self, "Salvato", "Configurazione Agente salvata!")

    def send_to_robot(self):
        text = self.chat_input.text().strip()
        if not text or not self.current_robot_name:
            return
        self.chat_display.append(f"<b style='color:#FFF'>👤 TU:</b> {text}<br>")
        self.chat_input.clear()

        if "chat_history" not in self.robots_data[self.current_robot_name]:
            self.robots_data[self.current_robot_name]["chat_history"] = []
        self.robots_data[self.current_robot_name]["chat_history"].append({"role": "user", "content": text})
        self.save_data()

        if self.controller:
            self.controller.process_robot_chat(self.current_robot_name, text)

    def receive_ai_reply(self, robot_name, reply):
        if robot_name == self.current_robot_name:
            self.chat_display.append(f"<b style='color:#00E676'>🤖 AGENTE:</b> {reply}<br>")
        self.robots_data[robot_name]["chat_history"].append({"role": "assistant", "content": reply})
        self.save_data()


# ============================================================================
#  4. MAPPING TAB
# ============================================================================
class MappingTab(QWidget):
    def __init__(self, controller):
        super().__init__()
        layout = create_scroll_layout(self)
        layout.addWidget(QLabel("🗺️ AI MAPPING"))
        self.inp = QLineEdit()
        self.inp.setPlaceholderText("URL del sito")
        layout.addWidget(self.inp)
        btn = QPushButton("Avvia Mappatura Automatica")
        btn.clicked.connect(lambda: controller.request_auto_mapping(self.inp.text()) if controller else None)
        layout.addWidget(btn)
        layout.addStretch()


# ============================================================================
#  5. STATS TAB
# ============================================================================
class StatsTab(QWidget):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        layout = create_scroll_layout(self)
        layout.addWidget(QLabel("📊 STATISTICHE SCOMMESSE"))
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Data", "Match", "Mercato", "Stake", "Esito"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setMinimumHeight(400)
        layout.addWidget(self.table)
        btn = QPushButton("Aggiorna")
        btn.clicked.connect(self.refresh)
        layout.addWidget(btn)

    def refresh(self):
        if self.controller and hasattr(self.controller, "get_bet_history"):
            hist = self.controller.get_bet_history()
            self.table.setRowCount(len(hist))
            for i, h in enumerate(reversed(hist)):
                self.table.setItem(i, 0, QTableWidgetItem(h.get("timestamp", "")))
                self.table.setItem(i, 1, QTableWidgetItem(h.get("teams", "")))
                self.table.setItem(i, 2, QTableWidgetItem(h.get("market", "")))
                self.table.setItem(i, 3, QTableWidgetItem(f"{h.get('stake', 0)}€"))
                self.table.setItem(i, 4, QTableWidgetItem(h.get("status", "")))


# ============================================================================
#  6. SETTINGS TAB (Vault Criptato)
# ============================================================================
class SettingsTab(QWidget):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        layout = create_scroll_layout(self)

        lbl = QLabel("⚙️ IMPOSTAZIONI SICUREZZA & API")
        lbl.setStyleSheet("font-size: 16px; font-weight: bold; color: #FFD700;")
        layout.addWidget(lbl)

        group = QGroupBox("Credenziali (Salvate in Vault Criptato AES-256)")
        form = QFormLayout(group)

        self.inp_or_key = QLineEdit()
        self.inp_or_key.setPlaceholderText("sk-or-v1-...")
        self.inp_or_key.setEchoMode(QLineEdit.Password)
        self.inp_tg_id = QLineEdit()
        self.inp_tg_id.setEchoMode(QLineEdit.Password)
        self.inp_tg_hash = QLineEdit()
        self.inp_tg_hash.setEchoMode(QLineEdit.Password)

        self.chk_show = QCheckBox("Mostra Chiavi")
        self.chk_show.stateChanged.connect(self.toggle_vis)

        form.addRow("OpenRouter Key:", self.inp_or_key)
        form.addRow("Telegram App ID:", self.inp_tg_id)
        form.addRow("Telegram App Hash:", self.inp_tg_hash)
        form.addRow("", self.chk_show)
        layout.addWidget(group)

        btn = QPushButton("💾 SALVA IN VAULT")
        btn.setStyleSheet("background-color: #2196F3; font-weight: bold; padding: 10px;")
        btn.clicked.connect(self.save_keys)
        layout.addWidget(btn)
        layout.addStretch()

        self.load_keys()

    def toggle_vis(self, state):
        mode = QLineEdit.Normal if state else QLineEdit.Password
        self.inp_or_key.setEchoMode(mode)
        self.inp_tg_id.setEchoMode(mode)
        self.inp_tg_hash.setEchoMode(mode)

    def load_keys(self):
        """Carica le chiavi dal Vault criptato."""
        try:
            vault = Vault()
            data = vault.decrypt_data()
            self.inp_or_key.setText(data.get("openrouter_api_key", ""))
            self.inp_tg_id.setText(data.get("telegram_api_id", ""))
            self.inp_tg_hash.setText(data.get("telegram_api_hash", ""))
        except Exception:
            pass

    def save_keys(self):
        """Salva le chiavi nel Vault criptato (AES-256)."""
        try:
            vault = Vault()
            data = {
                "openrouter_api_key": self.inp_or_key.text().strip(),
                "telegram_api_id": self.inp_tg_id.text().strip(),
                "telegram_api_hash": self.inp_tg_hash.text().strip()
            }
            if vault.encrypt_data(data):
                if self.controller:
                    self.controller.reload_secrets()
                QMessageBox.information(self, "OK", "Chiavi salvate nel Vault criptato!")
            else:
                QMessageBox.critical(self, "Errore", "Errore crittografia Vault.")
        except Exception as e:
            QMessageBox.critical(self, "Errore", str(e))


# ============================================================================
#  MAIN WINDOW
# ============================================================================
class MainWindow(QMainWindow):
    def __init__(self, logger=None, executor=None, config=None, monitor=None, controller=None):
        super().__init__()
        self.logger = logger
        self.controller = controller
        if self.controller:
            self.controller.ui_window = self

        self.setWindowTitle("SuperAgent V6.0 - Stable Edition")
        self.resize(1200, 800)
        self.setStyleSheet(STYLE_SHEET)

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)

        self.tabs = QTabWidget()
        self.factory = RobotFactoryTab(controller)
        self.supervisor = SupervisorTab(controller, self.factory)
        self.money = MoneyTab(controller)
        self.settings = SettingsTab(controller)
        self.mapping = MappingTab(controller)
        self.stats = StatsTab(controller)

        self.tabs.addTab(self.supervisor, "🛡️ SUPERVISOR")
        self.tabs.addTab(self.factory, "🏭 FACTORY")
        self.tabs.addTab(self.money, "💰 MONEY")
        self.tabs.addTab(self.settings, "⚙️ IMPOSTAZIONI")
        self.tabs.addTab(self.mapping, "🗺️ MAPPING")
        self.tabs.addTab(self.stats, "📊 STATS")

        main_layout.addWidget(self.tabs)

        if self.controller:
            self.controller.log_message.connect(self.supervisor.log.append)


def run_app(logger=None, executor=None, config=None, monitor=None, controller=None):
    app = QApplication.instance() or QApplication(sys.argv)
    win = MainWindow(logger, executor, config, monitor, controller)
    win.show()
    return app.exec()


if __name__ == "__main__":
    run_app()
