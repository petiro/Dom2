"""
SuperAgent Desktop App V5.6 - SENTINEL EDITION (FACTORY ENHANCED)
"""
import os
import sys
import re
import time
import queue
import json
import logging
import requests
import ctypes
from datetime import datetime
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from logging.handlers import RotatingFileHandler

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QPushButton, QLabel, QLineEdit, QGroupBox, QTabWidget,
    QTableWidget, QTableWidgetItem, QCheckBox, QMessageBox, QSpinBox,
    QProgressBar, QComboBox, QFormLayout, QSplitter, QDoubleSpinBox,
    QListWidget, QListWidgetItem, QFrame, QDialog, QDialogButtonBox,
    QSizePolicy, QScrollArea, QHeaderView
)
from PySide6.QtCore import Qt, Signal, QThread, QTimer, Slot, QSize, QObject, QEvent
from PySide6.QtGui import QFont, QColor, QPalette, QTextCursor, QIcon

# --- INTEGRAZIONE LOGGER ---
try:
    from core.logger import setup_logger
except ImportError:
    def setup_logger(): return logging.getLogger("Fallback"), None

# --- INTEGRAZIONE MONEY MANAGEMENT ---
try:
    from core.money_management import RoserpinaTable
except ImportError:
    class RoserpinaTable:
        def __init__(self, bankroll=100, stake=1): 
            self.bankroll = bankroll
            self.stake = stake
            self.strategy = "fixed"
        def set_strategy(self, strat): self.strategy = strat

# --- PATH SYSTEM ---
def get_project_root():
    if getattr(sys, 'frozen', False): return os.path.dirname(sys.executable)
    try: return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    except: return os.getcwd()

_ROOT_DIR = get_project_root()
LOG_DIR = os.path.join(_ROOT_DIR, "logs")
if not os.path.exists(LOG_DIR): os.makedirs(LOG_DIR, exist_ok=True)

ROBOTS_FILE = os.path.join(_ROOT_DIR, "config", "my_robots.json")
API_FILE = os.path.join(_ROOT_DIR, "config", "api_config.json")
TRAINING_DATA_FILE = os.path.join(_ROOT_DIR, "data", "learned_patterns.json")
LOG_FILE = os.path.join(LOG_DIR, "superagent_v5.log")

# --- SETUP GLOBAL FILE HANDLER ---
_fh = None
_logger = logging.getLogger("desktop_app")

try:
    _fh = RotatingFileHandler(
        LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s")
    _fh.setFormatter(formatter)
    _logger.addHandler(_fh)
    _logger.setLevel(logging.INFO)
    _logger.info(f"=== SUPERAGENT STARTED === ROOT: {_ROOT_DIR}")
except Exception as e:
    print(f"ERRORE CRITICO LOGGER: {e}")

# --- GLOBAL STYLESHEET (MODERN DARK) ---
STYLE_SHEET = """
QMainWindow, QWidget { background-color: #1e1e1e; color: #e0e0e0; font-family: 'Segoe UI', sans-serif; }
QTabWidget::pane { border: 1px solid #333; }
QTabBar::tab { background: #2d2d2d; color: #888; padding: 10px 20px; border-radius: 4px; margin-right: 2px; }
QTabBar::tab:selected { background: #3e3e3e; color: #4caf50; border-bottom: 2px solid #4caf50; font-weight: bold; }
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
    background-color: #333; color: white; border: 1px solid #444; border-radius: 4px; padding: 6px;
}
QLineEdit:focus, QSpinBox:focus { border: 1px solid #4caf50; }
QPushButton {
    background-color: #3a3a3a; color: white; border: 1px solid #555; padding: 8px 15px; border-radius: 4px;
}
QPushButton:hover { background-color: #444; border-color: #4caf50; }
QPushButton:pressed { background-color: #222; }
QTableWidget { background-color: #252526; gridline-color: #333; border: none; }
QHeaderView::section { background-color: #2d2d2d; padding: 6px; border: none; font-weight: bold; }
QGroupBox { border: 1px solid #444; border-radius: 6px; margin-top: 20px; font-weight: bold; }
QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }
QTextEdit { background-color: #1e1e1e; border: 1px solid #333; font-family: Consolas; }
"""

# ============================================================================
#  1. STATS TAB
# ============================================================================
class StatsTab(QWidget):
    def __init__(self, controller=None):
        super().__init__()
        self.controller = controller
        self.init_ui()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh_stats)
        self.timer.start(5000)

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        content = QWidget()
        layout = QVBoxLayout(content)

        kpi_layout = QHBoxLayout()
        self.lbl_bets = self._create_card("TOTAL BETS", "0")
        self.lbl_placed = self._create_card("PLACED", "0", "#2196F3")
        self.lbl_profit = self._create_card("PROFIT", "0.00 u", "#4CAF50")
        self.lbl_winrate = self._create_card("WIN RATE", "0%", "#FFC107")
        kpi_layout.addWidget(self.lbl_bets)
        kpi_layout.addWidget(self.lbl_placed)
        kpi_layout.addWidget(self.lbl_profit)
        kpi_layout.addWidget(self.lbl_winrate)
        layout.addLayout(kpi_layout)
        
        layout.addWidget(QLabel("📜 Storico Operazioni"))
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Ora", "Match", "Mercato", "Stake", "Esito"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setMinimumHeight(300)
        layout.addWidget(self.table)
        
        btn_ref = QPushButton("Aggiorna Ora")
        btn_ref.clicked.connect(self.refresh_stats)
        layout.addWidget(btn_ref)
        
        layout.addStretch()
        scroll.setWidget(content)
        main_layout.addWidget(scroll)

    def _create_card(self, title, val, color="#e0e0e0"):
        frame = QFrame()
        frame.setStyleSheet(f"background-color: #2d2d2d; border-radius: 8px; border-left: 5px solid {color};")
        lay = QVBoxLayout(frame)
        t = QLabel(title)
        t.setStyleSheet("font-size: 10px; color: #888;")
        v = QLabel(val)
        v.setStyleSheet(f"font-size: 22px; font-weight: bold; color: {color};")
        v.setAlignment(Qt.AlignCenter)
        lay.addWidget(t)
        lay.addWidget(v)
        return frame

    def refresh_stats(self):
        if not self.controller: return
        stats = self.controller.get_stats()
        history = self.controller.get_bet_history()
        self.lbl_bets.layout().itemAt(1).widget().setText(str(stats["bets_total"]))
        self.lbl_placed.layout().itemAt(1).widget().setText(str(stats["bets_placed"]))
        self.lbl_profit.layout().itemAt(1).widget().setText(f"{stats['total_profit']:.2f}")
        self.lbl_winrate.layout().itemAt(1).widget().setText(f"{stats['win_rate']:.1f}%")
        self.table.setRowCount(len(history))
        for i, row_data in enumerate(reversed(history)): 
            ts = datetime.fromtimestamp(row_data.get("timestamp", 0)).strftime("%H:%M:%S")
            self.table.setItem(i, 0, QTableWidgetItem(ts))
            self.table.setItem(i, 1, QTableWidgetItem(str(row_data.get("teams", "?"))))
            self.table.setItem(i, 2, QTableWidgetItem(str(row_data.get("market", "?"))))
            self.table.setItem(i, 3, QTableWidgetItem(str(row_data.get("stake", "0"))))
            res = "✅ PIAZZATA" if row_data.get("placed") else "❌ FALLITA"
            item_res = QTableWidgetItem(res)
            item_res.setForeground(QColor("#4CAF50") if row_data.get("placed") else QColor("#F44336"))
            self.table.setItem(i, 4, item_res)

# ============================================================================
#  2. MONEY TAB
# ============================================================================
class MoneyTab(QWidget):
    def __init__(self, controller=None):
        super().__init__()
        self.controller = controller
        self.config_file = os.path.join(get_project_root(), "config", "money_config.json")
        self.init_ui()
        self.load_settings()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        content = QWidget()
        layout = QVBoxLayout(content)

        gb_bank = QGroupBox("💰 Gestione Bankroll (Persistente)")
        form = QFormLayout(gb_bank)
        self.spin_bankroll = QDoubleSpinBox()
        self.spin_bankroll.setRange(0, 1000000)
        self.spin_bankroll.setPrefix("€ ")
        self.combo_strat = QComboBox()
        self.combo_strat.addItems(["Stake Fisso", "Masaniello", "Percentuale"])
        self.spin_stake = QDoubleSpinBox()
        self.spin_stake.setSuffix(" u")
        form.addRow("Bankroll Totale:", self.spin_bankroll)
        form.addRow("Strategia:", self.combo_strat)
        form.addRow("Stake Base / %:", self.spin_stake)
        btn_apply = QPushButton("💾 Salva e Applica")
        btn_apply.clicked.connect(self.apply_settings)
        btn_apply.setStyleSheet("background-color: #2196F3; color: white; font-weight: bold;")
        form.addRow(btn_apply)
        
        layout.addWidget(gb_bank)
        layout.addStretch()
        scroll.setWidget(content)
        main_layout.addWidget(scroll)

    def apply_settings(self):
        if not self.controller: return
        data = {
            "bankroll": self.spin_bankroll.value(),
            "strategy_index": self.combo_strat.currentIndex(),
            "strategy_name": self.combo_strat.currentText(),
            "stake": self.spin_stake.value()
        }
        try:
            folder = os.path.dirname(self.config_file)
            if not os.path.exists(folder): os.makedirs(folder, exist_ok=True)
            with open(self.config_file, "w") as f: json.dump(data, f, indent=4)
        except Exception as e:
            _logger.error(f"Errore salvataggio Money: {e}")
        if hasattr(self.controller, 'table'):
            self.controller.table.bankroll = data["bankroll"]
            self.controller.table.stake = data["stake"]
            strat_map = {"Stake Fisso": "fixed", "Masaniello": "masa", "Percentuale": "percent"}
            self.controller.table.strategy = strat_map.get(data["strategy_name"], "fixed")
            QMessageBox.information(self, "Salvato", "Configurazione Money salvata e applicata!")

    def load_settings(self):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, "r") as f:
                    data = json.load(f)
                    self.spin_bankroll.setValue(data.get("bankroll", 100))
                    self.combo_strat.setCurrentIndex(data.get("strategy_index", 0))
                    self.spin_stake.setValue(data.get("stake", 1))
            except: pass

# ============================================================================
#  3. SUPERVISOR TAB
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

        header = QFrame()
        header.setStyleSheet("background-color: #252526; padding: 10px; border-radius: 5px;")
        h_lay = QHBoxLayout(header)
        lbl_stat = QLabel("🛡️ SUPERVISOR SYSTEM")
        lbl_stat.setStyleSheet("font-weight: bold; font-size: 14px; color: #4CAF50;")
        btn_kill = QPushButton("☢️ EMERGENCY STOP")
        btn_kill.setMinimumHeight(40)
        btn_kill.setStyleSheet("QPushButton { background-color: #B71C1C; color: white; font-weight: bold; }")
        btn_kill.clicked.connect(self.kill_system)
        h_lay.addWidget(lbl_stat)
        h_lay.addStretch()
        h_lay.addWidget(btn_kill)
        layout.addWidget(header)
        
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setStyleSheet("background-color: #000; color: #0f0; font-family: 'Consolas'; font-size: 11px;")
        self.log.setMinimumHeight(400)
        layout.addWidget(self.log)
        
        layout.addStretch()
        scroll.setWidget(content)
        main_layout.addWidget(scroll)

    def kill_system(self):
        if QMessageBox.question(self, "STOP", "SEI SICURO?", QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            self.log.append("🚨 EMERGENCY STOP ACTIVATED")
            if self.controller: self.controller.shutdown()
            for name in self.factory.robots_data:
                self.factory.robots_data[name]["active"] = False
            self.factory.save_data()

# ============================================================================
#  4. TRAINER TAB
# ============================================================================
class TrainerTab(QWidget):
    def __init__(self, controller=None, logger=None):
        super().__init__()
        self.controller = controller
        self.logger = logger
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        content = QWidget()
        layout = QVBoxLayout(content)

        self.display = QTextEdit()
        self.display.setReadOnly(True)
        self.display.setPlaceholderText("Training output...")
        self.display.setMinimumHeight(300)
        layout.addWidget(self.display)
        
        btn_train = QPushButton("🧠 Esegui Training Step")
        btn_train.clicked.connect(self.run_training)
        layout.addWidget(btn_train)
        
        layout.addStretch()
        scroll.setWidget(content)
        main_layout.addWidget(scroll)
        
    def run_training(self):
        if self.controller:
            self.display.append("⏳ Training avviato...")
            self.controller.request_training()

    @Slot(str)
    def on_training_complete(self, result):
        self.display.append(f"\n✅ Training Completato:\n{result}")
        self.save_knowledge(result)

    def save_knowledge(self, content):
        try:
            entry = {"timestamp": datetime.now().isoformat(), "log": content}
            data = []
            if os.path.exists(TRAINING_DATA_FILE):
                with open(TRAINING_DATA_FILE, "r") as f:
                    try: data = json.load(f)
                    except: pass
            data.append(entry)
            os.makedirs(os.path.dirname(TRAINING_DATA_FILE), exist_ok=True)
            with open(TRAINING_DATA_FILE, "w") as f: json.dump(data, f, indent=4)
        except Exception as e: _logger.error(f"Errore salvataggio training: {e}")

# ============================================================================
#  5. FACTORY TAB (AGGIORNATA: CANCELLAZIONE + ISTRUZIONI) ✅
# ============================================================================
class RobotFactoryTab(QWidget):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self.robots_data = self._load_json(ROBOTS_FILE)
        self.current_robot = None
        self.init_ui()

    def _load_json(self, path):
        if os.path.exists(path):
            with open(path, "r") as f: return json.load(f)
        return {}

    def save_data(self):
        with open(ROBOTS_FILE, "w") as f: json.dump(self.robots_data, f, indent=4)

    def init_ui(self):
        main_layout = QHBoxLayout(self)
        
        # Lista Robot (Sinistra)
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        self.list_widget = QListWidget()
        self.list_widget.currentItemChanged.connect(self.load_robot)
        left_layout.addWidget(QLabel("🤖 AGENTI"))
        left_layout.addWidget(self.list_widget)
        btn_add = QPushButton("+ Crea Nuovo")
        btn_add.clicked.connect(self.create_robot)
        left_layout.addWidget(btn_add)
        
        # Dettagli (Destra) - SCROLLABLE
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        right_content = QWidget()
        right_layout = QVBoxLayout(right_content)

        self.right_group = QGroupBox("Dettagli & Istruzioni")
        self.right_group.setVisible(False)
        form = QFormLayout(self.right_group)
        
        self.inp_name = QLineEdit()
        self.inp_tg = QLineEdit()
        self.inp_tg.setPlaceholderText("@Canale")
        self.inp_site = QComboBox() 
        self.inp_site.addItems(["bet365", "goldbet", "planetwin365"])
        
        # NUOVO: CAMPO ISTRUZIONI (CHAT)
        self.inp_instructions = QTextEdit()
        self.inp_instructions.setPlaceholderText("Scrivi qui cosa deve fare questo robot...\nEs: 'Analizza solo quote > 2.00 su Tennis'")
        self.inp_instructions.setMinimumHeight(150)
        
        self.btn_active = QPushButton("ATTIVA")
        self.btn_active.setCheckable(True)
        self.btn_active.clicked.connect(self.toggle_active)
        
        # NUOVO: PULSANTE ELIMINA
        self.btn_delete = QPushButton("🗑️ ELIMINA ROBOT")
        self.btn_delete.setStyleSheet("background-color: #d32f2f; color: white; font-weight: bold;")
        self.btn_delete.clicked.connect(self.delete_robot)
        
        form.addRow("Nome:", self.inp_name)
        form.addRow("Telegram:", self.inp_tg)
        form.addRow("Sito Target:", self.inp_site)
        form.addRow("Istruzioni:", self.inp_instructions)
        form.addRow(self.btn_active)
        
        btn_save = QPushButton("Salva Modifiche")
        btn_save.clicked.connect(self.save_robot)
        form.addRow(btn_save)
        form.addRow(self.btn_delete) # Aggiunto in fondo
        
        right_layout.addWidget(self.right_group)
        right_layout.addStretch()
        scroll.setWidget(right_content)

        main_layout.addWidget(left_widget, 1)
        main_layout.addWidget(scroll, 2)
        self.refresh_list()

    def refresh_list(self):
        self.list_widget.clear()
        for name in self.robots_data: self.list_widget.addItem(name)

    def create_robot(self):
        name = f"Bot_{len(self.robots_data)+1}"
        self.robots_data[name] = {
            "telegram": "", 
            "active": False, 
            "target_site": "bet365",
            "instructions": ""
        }
        self.save_data()
        self.refresh_list()

    def load_robot(self, item, prev):
        if not item: return
        self.right_group.setVisible(True)
        name = item.text()
        self.current_robot = name
        data = self.robots_data[name]
        
        self.inp_name.setText(name)
        self.inp_tg.setText(data.get("telegram", ""))
        self.inp_instructions.setPlainText(data.get("instructions", "")) # CARICA ISTRUZIONI
        
        idx = self.inp_site.findText(data.get("target_site", "bet365"))
        if idx >= 0: self.inp_site.setCurrentIndex(idx)
        self.update_active_btn(data.get("active", False))

    def save_robot(self):
        if not self.current_robot: return
        new_name = self.inp_name.text()
        old_name = self.current_robot
        
        # Recupera dati esistenti o crea nuovi
        data = self.robots_data.get(old_name, {})
        data["telegram"] = self.inp_tg.text()
        data["target_site"] = self.inp_site.currentText()
        data["instructions"] = self.inp_instructions.toPlainText() # SALVA ISTRUZIONI
        
        if new_name != old_name:
            self.robots_data[new_name] = data
            if old_name in self.robots_data:
                del self.robots_data[old_name]
            self.current_robot = new_name
        else:
            self.robots_data[old_name] = data
            
        self.save_data()
        self.refresh_list()
        QMessageBox.information(self, "Info", "Agente salvato.")

    def delete_robot(self):
        if not self.current_robot: return
        reply = QMessageBox.question(self, "Conferma Eliminazione", 
                                     f"Sei sicuro di voler eliminare {self.current_robot}?\nQuesta azione è irreversibile.",
                                     QMessageBox.Yes | QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            if self.current_robot in self.robots_data:
                del self.robots_data[self.current_robot]
                self.save_data()
                self.refresh_list()
                self.right_group.setVisible(False)
                self.current_robot = None
                QMessageBox.information(self, "Info", "Agente eliminato.")

    def update_active_btn(self, active):
        self.btn_active.setText("🟢 ATTIVO" if active else "🔴 INATTIVO")
        self.btn_active.setChecked(active)

    def toggle_active(self):
        is_active = self.btn_active.isChecked()
        for name in self.robots_data: self.robots_data[name]["active"] = False
        self.robots_data[self.current_robot]["active"] = is_active
        self.update_active_btn(is_active)
        self.save_data()
        
        if is_active and self.controller:
            data = self.robots_data[self.current_robot]
            data["name"] = self.current_robot
            self.controller.load_robot_profile(data)
            QMessageBox.information(self, "OK", f"{self.current_robot} Attivato!\nIstruzioni caricate nel sistema.")

# ============================================================================
#  MAIN WINDOW
# ============================================================================
class MainWindow(QMainWindow):
    def __init__(self, vision=None, telegram_learner=None, rpa_healer=None,
                 logger=None, executor=None, config=None, monitor=None,
                 controller=None):
        super().__init__()
        self.controller = controller
        self.setWindowTitle("SuperAgent V5.6 Sentinel")
        self.resize(1100, 750)
        self.setStyleSheet(STYLE_SHEET)
        self.logger_engine, self.qt_handler = setup_logger()

        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        self.factory = RobotFactoryTab(controller)
        self.supervisor = SupervisorTab(controller, self.factory)
        self.stats_tab = StatsTab(controller)
        self.money_tab = MoneyTab(controller)
        self.trainer_tab = TrainerTab(controller, logger)
        
        try:
            from ui.mapping_tab import MappingTab
            from ui.telegram_tab import TelegramTab
            self.mapping_tab = MappingTab(controller)
            self.telegram_tab = TelegramTab(controller=controller)
        except ImportError:
            self.mapping_tab = QWidget()
            self.telegram_tab = QWidget()

        self.tabs.addTab(self.supervisor, "📡 SUPERVISOR")
        self.tabs.addTab(self.factory, "🤖 FACTORY")
        self.tabs.addTab(self.stats_tab, "📊 STATS")
        self.tabs.addTab(self.money_tab, "💰 MONEY")
        self.tabs.addTab(self.telegram_tab, "✈️ TELEGRAM")
        self.tabs.addTab(self.mapping_tab, "🗺️ MAPPING")
        self.tabs.addTab(self.trainer_tab, "🧠 TRAINER")
        
        if self.qt_handler:
            self.qt_handler.log_signal.connect(self.update_gui_log)
        if self.controller:
            self.controller.training_complete.connect(self.trainer_tab.on_training_complete)

    @Slot(str, str)
    def update_gui_log(self, level, msg):
        if hasattr(self, 'supervisor'):
            color = "#4CAF50" if level == "INFO" else "#F44336" if level in ["ERROR", "CRITICAL"] else "#FFC107"
            self.supervisor.log.append(f"<span style='color:{color}'>[{datetime.now().strftime('%H:%M:%S')}] {msg}</span>")

    def closeEvent(self, event):
        if self.controller: self.controller.shutdown()
        super().closeEvent(event)

# ============================================================================
#  GLOBAL SPY
# ============================================================================
class GlobalSpy(QObject):
    def __init__(self, logger):
        super().__init__()
        self.logger = logger
    def eventFilter(self, obj, event):
        if event.type() == QEvent.MouseButtonPress:
            try: self.logger.info(f"🖱️ CLICK: {obj.objectName() or obj.metaObject().className()}")
            except: pass
        return super().eventFilter(obj, event)

def apply_dark_theme(app):
    p = QPalette()
    p.setColor(QPalette.Window, QColor(53, 53, 53))
    p.setColor(QPalette.WindowText, Qt.white)
    p.setColor(QPalette.Base, QColor(25, 25, 25))
    p.setColor(QPalette.AlternateBase, QColor(53, 53, 53))
    p.setColor(QPalette.ToolTipBase, Qt.white)
    p.setColor(QPalette.ToolTipText, Qt.white)
    p.setColor(QPalette.Text, Qt.white)
    p.setColor(QPalette.Button, QColor(53, 53, 53))
    p.setColor(QPalette.ButtonText, Qt.white)
    p.setColor(QPalette.BrightText, Qt.red)
    p.setColor(QPalette.Link, QColor(42, 130, 218))
    p.setColor(QPalette.Highlight, QColor(42, 130, 218))
    p.setColor(QPalette.HighlightedText, Qt.black)
    app.setPalette(p)

def run_app(vision=None, telegram_learner=None, rpa_healer=None,
            logger=None, executor=None, config=None, monitor=None,
            controller=None):
    
    import ctypes
    try: ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except: pass
    
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    apply_dark_theme(app)
    
    try:
        from core.logger import setup_logger
        logger_engine, _ = setup_logger()
        global _fh
        if '_fh' in globals() and _fh:
            if _fh not in logger_engine.handlers:
                logger_engine.addHandler(_fh)
    except:
        logger_engine = logging.getLogger("Fallback")

    spy = GlobalSpy(logger_engine)
    app.installEventFilter(spy)

    win = MainWindow(vision, telegram_learner, rpa_healer,
                     logger, executor, config, monitor, controller)
    win.showMaximized()
    return app.exec()
