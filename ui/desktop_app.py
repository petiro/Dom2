"""
SuperAgent Desktop App V5.7 - LIVE MODE SWITCH
"""
import os
import sys
import json
import logging
from datetime import datetime
from logging.handlers import RotatingFileHandler

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QPushButton, QLabel, QLineEdit, QGroupBox, QTabWidget,
    QTableWidget, QTableWidgetItem, QMessageBox, QComboBox, QFormLayout,
    QListWidget, QFrame, QScrollArea, QHeaderView, QRadioButton, QButtonGroup
)
from PySide6.QtCore import Qt, Signal, QTimer, Slot, QObject, QEvent
from PySide6.QtGui import QColor, QPalette

# --- INTEGRAZIONE LOGGER ---
try:
    from core.logger import setup_logger
except ImportError:
    def setup_logger(): return logging.getLogger("Fallback"), None

# --- PATH SYSTEM ---
def get_project_root():
    if getattr(sys, 'frozen', False): return os.path.dirname(sys.executable)
    try: return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    except: return os.getcwd()

_ROOT_DIR = get_project_root()
LOG_DIR = os.path.join(_ROOT_DIR, "logs")
if not os.path.exists(LOG_DIR): os.makedirs(LOG_DIR, exist_ok=True)

ROBOTS_FILE = os.path.join(_ROOT_DIR, "config", "my_robots.json")
LOG_FILE = os.path.join(LOG_DIR, "superagent_v5.log")

# --- STYLESHEET ---
STYLE_SHEET = """
QMainWindow, QWidget { background-color: #1e1e1e; color: #e0e0e0; font-family: 'Segoe UI', sans-serif; }
QTabWidget::pane { border: 1px solid #333; }
QTabBar::tab { background: #2d2d2d; color: #888; padding: 10px 20px; border-radius: 4px; margin-right: 2px; }
QTabBar::tab:selected { background: #3e3e3e; color: #4caf50; border-bottom: 2px solid #4caf50; font-weight: bold; }
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox { background-color: #333; color: white; border: 1px solid #444; border-radius: 4px; padding: 6px; }
QLineEdit:focus, QSpinBox:focus { border: 1px solid #4caf50; }
QPushButton { background-color: #3a3a3a; color: white; border: 1px solid #555; padding: 8px 15px; border-radius: 4px; }
QPushButton:hover { background-color: #444; border-color: #4caf50; }
QGroupBox { border: 1px solid #444; border-radius: 6px; margin-top: 20px; font-weight: bold; }
QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }
QTextEdit { background-color: #1e1e1e; border: 1px solid #333; font-family: Consolas; }
"""

# ============================================================================
#  SUPERVISOR TAB (CON LIVE SWITCH)
# ============================================================================
class SupervisorTab(QWidget):
    def __init__(self, controller, factory):
        super().__init__()
        self.controller = controller
        self.factory = factory
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        content = QWidget()
        layout = QVBoxLayout(content)

        # --- HEADER CON PULSANTI ---
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
        
        # Connetti il cambio modalità al controller
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
        
        layout.addWidget(header)
        
        # --- LOG CONSOLE ---
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setStyleSheet("background-color: #000; color: #0f0; font-family: 'Consolas'; font-size: 11px;")
        self.log.setMinimumHeight(400)
        layout.addWidget(self.log)
        
        layout.addStretch()
        scroll.setWidget(content)
        main_layout.addWidget(scroll)

    def on_mode_changed(self, btn, checked):
        if checked:
            is_live = (btn == self.rb_live)
            if self.controller:
                self.controller.set_live_mode(is_live)
                if is_live:
                    self.log.append("<span style='color:red'>⚠️ ATTENZIONE: MODALITÀ LIVE ATTIVATA. IL BOT ORA PIAZZA SCOMMESSE REALI.</span>")
                else:
                    self.log.append("<span style='color:green'>🛡️ MODALITÀ DEMO ATTIVATA. Scommesse simulate.</span>")

    def kill_system(self):
        if QMessageBox.question(self, "STOP", "SEI SICURO?", QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            self.log.append("🚨 EMERGENCY STOP ACTIVATED")
            if self.controller: self.controller.shutdown()
            for name in self.factory.robots_data:
                self.factory.robots_data[name]["active"] = False
            self.factory.save_data()

# ============================================================================
#  ALTRE TAB (Standard - Incolla qui sotto il codice standard se necessario, 
#  oppure usa il file desktop_app.py che avevi, sostituendo solo SupervisorTab)
#  Per brevità includo i placeholder per le altre classi necessarie al run
# ============================================================================

class StatsTab(QWidget):
    def __init__(self, c=None): super().__init__()
class MoneyTab(QWidget):
    def __init__(self, c=None): super().__init__()
class TrainerTab(QWidget):
    def __init__(self, c=None, l=None): 
        super().__init__()
        self.on_training_complete = lambda x: None
class RobotFactoryTab(QWidget):
    def __init__(self, c): 
        super().__init__()
        self.robots_data = {}
        self.save_data = lambda: None

# IMPORTANTE: Se stai sovrascrivendo l'intero file, assicurati di rimettere
# le classi StatsTab, MoneyTab, TrainerTab, RobotFactoryTab e MainWindow complete 
# dal codice precedente. La modifica chiave è SOLO nella classe SupervisorTab qui sopra.

# ... (Il resto del codice di desktop_app.py rimane invariato) ...
# Per evitare errori, riutilizza il MainWindow del codice precedente ma con la SupervisorTab aggiornata.
