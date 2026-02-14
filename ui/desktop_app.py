"""
SuperAgent Desktop App V5.7 - COMPLETE EDITION
- Supervisor: Live/Demo Switch + Emergency Stop
- Money: Roserpina Real Logic (Resa/Prese)
- Factory: Robot Management
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
    QDoubleSpinBox, QSpinBox, QCheckBox
)
from PySide6.QtCore import Qt, Signal, QTimer, Slot, QObject, QEvent
from PySide6.QtGui import QColor, QPalette, QFont

# --- UTILS ---
def get_project_root():
    if getattr(sys, 'frozen', False): return os.path.dirname(sys.executable)
    try: return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    except: return os.getcwd()

_ROOT_DIR = get_project_root()
LOG_DIR = os.path.join(_ROOT_DIR, "logs")
if not os.path.exists(LOG_DIR): os.makedirs(LOG_DIR, exist_ok=True)
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
"""

# ============================================================================
#  1. SUPERVISOR TAB (Live Switch + Logs)
# ============================================================================
class SupervisorTab(QWidget):
    def __init__(self, controller, factory):
        super().__init__()
        self.controller = controller
        self.factory = factory
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        
        # --- HEADER ---
        header = QFrame()
        header.setStyleSheet("background-color: #252526; padding: 10px; border-radius: 5px;")
        h_lay = QHBoxLayout(header)
        
        lbl_stat = QLabel("🛡️ SUPERVISOR SYSTEM")
        lbl_stat.setStyleSheet("font-weight: bold; font-size: 14px; color: #4CAF50;")
        
        # --- SWITCH DEMO/LIVE ---
        self.mode_group = QButtonGroup(self)
        self.rb_demo = QRadioButton("🛡️ DEMO (Safe)")
        self.rb_live = QRadioButton("💸 LIVE (Soldi Veri)")
        
        self.rb_demo.setChecked(True) # Default sicuro
        self.rb_demo.setStyleSheet("color: #4CAF50; font-weight: bold;")
        self.rb_live.setStyleSheet("color: #F44336; font-weight: bold;")
        
        self.mode_group.addButton(self.rb_demo)
        self.mode_group.addButton(self.rb_live)
        self.mode_group.buttonToggled.connect(self.on_mode_changed)

        h_lay.addWidget(lbl_stat)
        h_lay.addStretch()
        h_lay.addWidget(QLabel("Modalità:"))
        h_lay.addWidget(self.rb_demo)
        h_lay.addWidget(self.rb_live)
        h_lay.addStretch()

        # --- EMERGENCY STOP ---
        btn_kill = QPushButton("☢️ EMERGENCY STOP")
        btn_kill.setMinimumHeight(40)
        btn_kill.setStyleSheet("QPushButton { background-color: #B71C1C; color: white; font-weight: bold; }")
        btn_kill.clicked.connect(self.kill_system)
        h_lay.addWidget(btn_kill)
        
        main_layout.addWidget(header)
        
        # --- LOG CONSOLE ---
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setStyleSheet("background-color: #000; color: #0f0; font-family: 'Consolas'; font-size: 11px;")
        main_layout.addWidget(self.log)

    def on_mode_changed(self, btn, checked):
        if checked:
            is_live = (btn == self.rb_live)
            if self.controller and hasattr(self.controller, "set_live_mode"):
                self.controller.set_live_mode(is_live)
                if is_live:
                    self.log.append("<span style='color:red'>⚠️ ATTENZIONE: MODALITÀ LIVE ATTIVATA. IL BOT ORA PIAZZA SCOMMESSE REALI.</span>")
                else:
                    self.log.append("<span style='color:green'>🛡️ MODALITÀ DEMO ATTIVATA. Scommesse simulate.</span>")

    def kill_system(self):
        if QMessageBox.question(self, "STOP", "SEI SICURO? Questo arresterà tutto.", QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            self.log.append("🚨 EMERGENCY STOP ACTIVATED")
            if self.controller: self.controller.shutdown()
            # Disattiva robot
            if self.factory:
                for name in self.factory.robots_data:
                    self.factory.robots_data[name]["active"] = False
                self.factory.save_data()

# ============================================================================
#  2. MONEY TAB (Roserpina Real Logic)
# ============================================================================
class MoneyTab(QWidget):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self.init_ui()
        self.load_config()

    def init_ui(self):
        layout = QVBoxLayout(self)

        lbl_title = QLabel("💰 GESTIONE CAPITALE (ROSERPINA)")
        lbl_title.setStyleSheet("font-size: 18px; font-weight: bold; color: #FFD700;")
        layout.addWidget(lbl_title)

        group_params = QGroupBox("Parametri Roserpina")
        form_params = QFormLayout(group_params)

        # 1. Capitale (Bankroll)
        self.sb_bankroll = QDoubleSpinBox()
        self.sb_bankroll.setRange(10, 100000)
        self.sb_bankroll.setValue(100.0)
        self.sb_bankroll.setPrefix("€ ")
        self.sb_bankroll.setStyleSheet("font-weight: bold; font-size: 14px; color: #FFF;")

        # 2. Resa Desiderata (Target Profitto Totale)
        self.sb_target_pct = QDoubleSpinBox()
        self.sb_target_pct.setRange(1, 500)
        self.sb_target_pct.setValue(45.0) # Esempio 45%
        self.sb_target_pct.setSuffix("% (Resa)")
        self.sb_target_pct.setStyleSheet("font-weight: bold; color: #FFD700;")
        
        # 3. Numero di Prese (Vittorie necessarie)
        self.sb_wins_needed = QSpinBox()
        self.sb_wins_needed.setRange(1, 20)
        self.sb_wins_needed.setValue(3)
        self.sb_wins_needed.setSuffix(" Prese")
        self.sb_wins_needed.setStyleSheet("font-weight: bold; color: #4CAF50;")

        form_params.addRow("🏦 Budget Iniziale:", self.sb_bankroll)
        form_params.addRow("🎯 Resa Obiettivo (%):", self.sb_target_pct)
        form_params.addRow("✅ Prese da fare:", self.sb_wins_needed)
        
        layout.addWidget(group_params)

        # Info
        self.lbl_info = QLabel("ℹ️ La strategia calcola lo stake per ottenere la Resa indicata nel numero di Prese specificato.")
        self.lbl_info.setWordWrap(True)
        self.lbl_info.setStyleSheet("color: #aaa; margin: 10px;")
        layout.addWidget(self.lbl_info)

        # Save Button
        btn_save = QPushButton("💾 SALVA CONFIGURAZIONE")
        btn_save.setStyleSheet("background-color: #2196F3; font-weight: bold; padding: 10px;")
        btn_save.clicked.connect(self.save_config)
        layout.addWidget(btn_save)
        
        # Reset Button
        btn_reset = QPushButton("♻️ RESET CICLO")
        btn_reset.setStyleSheet("background-color: #555; margin-top: 5px;")
        btn_reset.clicked.connect(self.reset_cycle_data)
        layout.addWidget(btn_reset)

        layout.addStretch()

    def save_config(self):
        data = {
            "strategy": "Roserpina", # Forziamo Roserpina per questa UI
            "bankroll": self.sb_bankroll.value(),
            "target_pct": self.sb_target_pct.value(),
            "wins_needed": self.sb_wins_needed.value()
        }
        
        try:
            os.makedirs("config", exist_ok=True)
            with open("config/money_config.json", "w") as f:
                json.dump(data, f, indent=4)
            
            if self.controller and hasattr(self.controller, "reload_money_manager"):
                self.controller.reload_money_manager()
                
            QMessageBox.information(self, "Salvato", "Configurazione Roserpina Aggiornata!")
        except Exception as e:
            QMessageBox.critical(self, "Errore", f"Impossibile salvare: {e}")

    def reset_cycle_data(self):
        if QMessageBox.question(self, "Reset", "Resettare il ciclo? Si riparte da zero.", QMessageBox.Yes|QMessageBox.No) == QMessageBox.Yes:
            try:
                if os.path.exists("config/roserpina_real_state.json"):
                    os.remove("config/roserpina_real_state.json")
                if self.controller and hasattr(self.controller, "reload_money_manager"):
                    self.controller.reload_money_manager()
            except: pass

    def load_config(self):
        if os.path.exists("config/money_config.json"):
            try:
                with open("config/money_config.json", "r") as f:
                    data = json.load(f)
                    self.sb_bankroll.setValue(float(data.get("bankroll", 100.0)))
                    self.sb_target_pct.setValue(float(data.get("target_pct", 45.0)))
                    self.sb_wins_needed.setValue(int(data.get("wins_needed", 3)))
            except: pass

# ============================================================================
#  3. FACTORY TAB (Gestione Robot)
# ============================================================================
class RobotFactoryTab(QWidget):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self.robots_data = {}
        self.init_ui()
        self.load_data()

    def init_ui(self):
        layout = QHBoxLayout(self)
        
        # List Panel
        left_panel = QFrame()
        left_layout = QVBoxLayout(left_panel)
        left_layout.addWidget(QLabel("🤖 I TUOI ROBOT"))
        self.robot_list = QListWidget()
        self.robot_list.currentItemChanged.connect(self.on_robot_select)
        left_layout.addWidget(self.robot_list)
        
        btn_add = QPushButton("+ NUOVO ROBOT")
        btn_add.clicked.connect(self.new_robot)
        left_layout.addWidget(btn_add)
        
        btn_del = QPushButton("🗑 ELIMINA")
        btn_del.setStyleSheet("background-color: #d32f2f;")
        btn_del.clicked.connect(self.delete_robot)
        left_layout.addWidget(btn_del)
        
        layout.addWidget(left_panel, 1)
        
        # Detail Panel
        self.right_panel = QGroupBox("Dettagli Robot")
        right_layout = QVBoxLayout(self.right_panel)
        
        self.inp_name = QLineEdit()
        self.inp_name.setPlaceholderText("Nome Robot (es. cecchino_over)")
        right_layout.addWidget(QLabel("Nome:"))
        right_layout.addWidget(self.inp_name)
        
        self.inp_instr = QTextEdit()
        self.inp_instr.setPlaceholderText("Es: 'Analizza Inter-Milan, se quota Over 2.5 > 1.80 scommetti'")
        right_layout.addWidget(QLabel("Istruzioni (Prompt):"))
        right_layout.addWidget(self.inp_instr)
        
        self.chk_active = QCheckBox("Attivo")
        right_layout.addWidget(self.chk_active)
        
        btn_save = QPushButton("SALVA ROBOT")
        btn_save.clicked.connect(self.save_current)
        right_layout.addWidget(btn_save)
        
        layout.addWidget(self.right_panel, 2)

    def load_data(self):
        if os.path.exists(ROBOTS_FILE):
            try:
                with open(ROBOTS_FILE, 'r') as f: self.robots_data = json.load(f)
                self.refresh_list()
            except: pass

    def save_data(self):
        try:
            with open(ROBOTS_FILE, 'w') as f: json.dump(self.robots_data, f, indent=4)
        except: pass

    def refresh_list(self):
        self.robot_list.clear()
        for name in self.robots_data:
            self.robot_list.addItem(name)

    def on_robot_select(self, current, previous):
        if not current: return
        name = current.text()
        data = self.robots_data.get(name, {})
        self.inp_name.setText(name)
        self.inp_instr.setText(data.get("instructions", ""))
        self.chk_active.setChecked(data.get("active", True))

    def new_robot(self):
        name = f"Robot_{len(self.robots_data)+1}"
        self.robots_data[name] = {"instructions": "", "active": False}
        self.save_data()
        self.refresh_list()

    def delete_robot(self):
        row = self.robot_list.currentRow()
        if row >= 0:
            name = self.robot_list.currentItem().text()
            del self.robots_data[name]
            self.save_data()
            self.refresh_list()

    def save_current(self):
        old_name = ""
        if self.robot_list.currentItem():
            old_name = self.robot_list.currentItem().text()
            
        new_name = self.inp_name.text().strip()
        if not new_name: return
        
        if old_name and old_name != new_name and old_name in self.robots_data:
            del self.robots_data[old_name]
            
        self.robots_data[new_name] = {
            "instructions": self.inp_instr.toPlainText(),
            "active": self.chk_active.isChecked()
        }
        self.save_data()
        self.refresh_list()

# ============================================================================
#  4. TRAINER & STATS (Tab secondarie)
# ============================================================================
class TrainerTab(QWidget):
    def __init__(self, controller, logger):
        super().__init__()
        self.controller = controller
        l = QVBoxLayout(self)
        l.addWidget(QLabel("🧠 ADDESTRAMENTO AI"))
        self.txt = QTextEdit()
        self.txt.setPlaceholderText("Incolla qui errori o scenari...")
        l.addWidget(self.txt)
        btn = QPushButton("Invia ad Addestramento")
        btn.clicked.connect(lambda: self.controller.request_training() if self.controller else None)
        l.addWidget(btn)

class MappingTab(QWidget):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        l = QVBoxLayout(self)
        l.addWidget(QLabel("🗺️ AI MAPPING"))
        self.inp = QLineEdit()
        self.inp.setPlaceholderText("URL del sito (es. https://www.goldbet.it)")
        l.addWidget(self.inp)
        btn = QPushButton("Avvia Mappatura Automatica")
        btn.clicked.connect(lambda: self.controller.request_auto_mapping(self.inp.text()) if self.controller else None)
        l.addWidget(btn)

class StatsTab(QWidget):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        l = QVBoxLayout(self)
        l.addWidget(QLabel("📊 STATISTICHE"))
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Data", "Match", "Esito"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        l.addWidget(self.table)
        btn = QPushButton("Aggiorna")
        btn.clicked.connect(self.refresh)
        l.addWidget(btn)
    
    def refresh(self):
        if self.controller and hasattr(self.controller, "get_bet_history"):
            hist = self.controller.get_bet_history()
            self.table.setRowCount(len(hist))
            for i, h in enumerate(hist):
                self.table.setItem(i, 0, QTableWidgetItem(str(datetime.now().strftime("%H:%M"))))
                self.table.setItem(i, 1, QTableWidgetItem(str(h.get("teams", "?"))))
                self.table.setItem(i, 2, QTableWidgetItem("Pending"))

# ============================================================================
#  MAIN WINDOW
# ============================================================================
class MainWindow(QMainWindow):
    def __init__(self, logger=None, executor=None, config=None, monitor=None, controller=None):
        super().__init__()
        self.logger = logger
        self.controller = controller
        self.setWindowTitle("SuperAgent V5.7 - Sentinel Core")
        self.resize(1200, 800)
        self.setStyleSheet(STYLE_SHEET)

        # Central Widget
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)

        # Tabs
        self.tabs = QTabWidget()
        
        # Init Tabs
        self.factory = RobotFactoryTab(controller)
        self.supervisor = SupervisorTab(controller, self.factory)
        self.money = MoneyTab(controller)
        self.trainer = TrainerTab(controller, logger)
        self.mapping = MappingTab(controller)
        self.stats = StatsTab(controller)

        self.tabs.addTab(self.supervisor, "🛡️ SUPERVISOR")
        self.tabs.addTab(self.factory, "🏭 FACTORY")
        self.tabs.addTab(self.money, "💰 MONEY")
        self.tabs.addTab(self.trainer, "🧠 TRAINER")
        self.tabs.addTab(self.mapping, "🗺️ MAPPING")
        self.tabs.addTab(self.stats, "📊 STATS")

        main_layout.addWidget(self.tabs)
        
        # Connect Log
        if self.controller:
            self.controller.log_message.connect(self.supervisor.log.append)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())
