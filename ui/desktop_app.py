"""
SuperAgent Desktop App V5.5 - SENTINEL EDITION (REAL LOGIC IMPLEMENTED & FIXED)
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
    # Fallback se manca il core
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

_logger = logging.getLogger("desktop_app")

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
#  1. STATS TAB (REALE)
# ============================================================================
class StatsTab(QWidget):
    def __init__(self, controller=None):
        super().__init__()
        self.controller = controller
        self.init_ui()
        
        # Timer aggiornamento real-time
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh_stats)
        self.timer.start(5000) # Ogni 5 secondi

    def init_ui(self):
        layout = QVBoxLayout(self)

        # --- KPI CARDS ---
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

        # --- HISTORY TABLE ---
        layout.addWidget(QLabel("📜 Storico Operazioni"))
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Ora", "Match", "Mercato", "Stake", "Esito"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.table)
        
        # Pulsante refresh manuale
        btn_ref = QPushButton("Aggiorna Ora")
        btn_ref.clicked.connect(self.refresh_stats)
        layout.addWidget(btn_ref)

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

        # 1. Recupera dati dal Controller
        stats = self.controller.get_stats()
        history = self.controller.get_bet_history()

        # 2. Aggiorna KPI (hacky object access to children labels)
        self.lbl_bets.findChild(QLabel, "").setText(str(stats["bets_total"])) 
        # Fix rapido per accedere al valore corretto:
        self.lbl_bets.layout().itemAt(1).widget().setText(str(stats["bets_total"]))
        self.lbl_placed.layout().itemAt(1).widget().setText(str(stats["bets_placed"]))
        self.lbl_profit.layout().itemAt(1).widget().setText(f"{stats['total_profit']:.2f}")
        self.lbl_winrate.layout().itemAt(1).widget().setText(f"{stats['win_rate']:.1f}%")

        # 3. Aggiorna Tabella
        self.table.setRowCount(len(history))
        for i, row_data in enumerate(reversed(history)): # Mostra ultimi in alto
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
#  2. MONEY TAB (ROSERPINA CONTROLLER - PERSISTENTE ✅)
# ============================================================================
class MoneyTab(QWidget):
    def __init__(self, controller=None):
        super().__init__()
        self.controller = controller
        self.config_file = os.path.join(get_project_root(), "config", "money_config.json")
        self.init_ui()
        self.load_settings() # <--- Carica all'avvio

    def init_ui(self):
        layout = QVBoxLayout(self)
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

    def apply_settings(self):
        if not self.controller: return
        
        data = {
            "bankroll": self.spin_bankroll.value(),
            "strategy_index": self.combo_strat.currentIndex(),
            "strategy_name": self.combo_strat.currentText(),
            "stake": self.spin_stake.value()
        }
        
        # 1. Salva su Disco
        try:
            folder = os.path.dirname(self.config_file)
            if not os.path.exists(folder): os.makedirs(folder, exist_ok=True)
            with open(self.config_file, "w") as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            _logger.error(f"Errore salvataggio Money: {e}")

        # 2. Applica al Controller
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
#  3. SUPERVISOR TAB (REAL KILL SWITCH)
# ============================================================================
class SupervisorTab(QWidget):
    def __init__(self, controller, factory):
        super().__init__()
        self.controller = controller
        self.factory = factory
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        # Header con Kill Switch
        header = QFrame()
        header.setStyleSheet("background-color: #252526; padding: 10px; border-radius: 5px;")
        h_lay = QHBoxLayout(header)
        
        lbl_stat = QLabel("🛡️ SUPERVISOR SYSTEM")
        lbl_stat.setStyleSheet("font-weight: bold; font-size: 14px; color: #4CAF50;")
        
        btn_kill = QPushButton("☢️ EMERGENCY STOP")
        btn_kill.setMinimumHeight(40)
        btn_kill.setStyleSheet("""
            QPushButton { background-color: #B71C1C; color: white; font-weight: bold; border: 2px solid #FF5252; }
            QPushButton:hover { background-color: #D32F2F; }
        """)
        btn_kill.clicked.connect(self.kill_system)
        
        h_lay.addWidget(lbl_stat)
        h_lay.addStretch()
        h_lay.addWidget(btn_kill)
        layout.addWidget(header)

        # Log Console
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setStyleSheet("background-color: #000; color: #0f0; font-family: 'Consolas'; font-size: 11px;")
        layout.addWidget(self.log)

    def kill_system(self):
        reply = QMessageBox.question(self, "CONFERMA STOP", 
                                     "SEI SICURO? Questo ucciderà tutti i processi attivi.",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.log.append("🚨 INIZIO PROCEDURA DI ARRESTO DI EMERGENZA...")
            
            # 1. Stop Controller
            if self.controller:
                self.controller.shutdown()
                self.log.append("✅ Controller Shutdown Signal Inviato")
            
            # 2. Stop Factory Robots
            for name in self.factory.robots_data:
                self.factory.robots_data[name]["active"] = False
            self.factory.save_data()
            self.log.append("✅ Tutti i Robot disattivati")


# ============================================================================
#  4. TRAINER TAB (PERSISTENCE)
# ============================================================================
class TrainerTab(QWidget):
    def __init__(self, controller=None, logger=None):
        super().__init__()
        self.controller = controller
        self.logger = logger
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        
        self.display = QTextEdit()
        self.display.setReadOnly(True)
        self.display.setPlaceholderText("I risultati del training appariranno qui...")
        layout.addWidget(self.display)
        
        btn_train = QPushButton("🧠 Esegui Training Step")
        btn_train.setMinimumHeight(50)
        btn_train.setStyleSheet("background-color: #673AB7; color: white; font-weight: bold;")
        btn_train.clicked.connect(self.run_training)
        layout.addWidget(btn_train)
        
        btn_save = QPushButton("💾 Salva Conoscenza Acquisita")
        btn_save.clicked.connect(self.save_knowledge)
        layout.addWidget(btn_save)

    def run_training(self):
        if self.controller:
            self.display.append("⏳ Training avviato... attendere...")
            self.controller.request_training()
        else:
            self.display.append("❌ Controller non disponibile.")

    @Slot(str)
    def on_training_complete(self, result):
        self.display.append(f"\n✅ TRAINING COMPLETATO:\n{result}")
        # Auto-salvataggio opzionale
        self.save_knowledge(auto=True)

    def save_knowledge(self, auto=False):
        content = self.display.toPlainText()
        if not content: return
        
        try:
            timestamp = datetime.now().isoformat()
            entry = {"timestamp": timestamp, "log": content}
            
            # Leggi esistente
            data = []
            if os.path.exists(TRAINING_DATA_FILE):
                with open(TRAINING_DATA_FILE, "r") as f:
                    try: data = json.load(f)
                    except: pass
            
            data.append(entry)
            
            # Scrivi
            os.makedirs(os.path.dirname(TRAINING_DATA_FILE), exist_ok=True)
            with open(TRAINING_DATA_FILE, "w") as f:
                json.dump(data, f, indent=4)
                
            if not auto: QMessageBox.information(self, "Salvato", "Conoscenza salvata in learned_patterns.json")
            
        except Exception as e:
            if not auto: QMessageBox.critical(self, "Errore", f"Errore salvataggio: {e}")


# ============================================================================
#  5. FACTORY TAB (CONNECTED TO CONTROLLER)
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
        layout = QHBoxLayout(self)
        
        # Lista Robot
        left_panel = QVBoxLayout()
        self.list_widget = QListWidget()
        self.list_widget.currentItemChanged.connect(self.load_robot)
        left_panel.addWidget(QLabel("🤖 I TUOI AGENTI"))
        left_panel.addWidget(self.list_widget)
        
        btn_add = QPushButton("+ Crea Nuovo")
        btn_add.clicked.connect(self.create_robot)
        left_panel.addWidget(btn_add)
        
        # Dettagli Robot
        self.right_panel = QGroupBox("Dettagli Agente")
        self.right_panel.setVisible(False)
        form = QFormLayout(self.right_panel)
        
        self.inp_name = QLineEdit()
        self.inp_tg = QLineEdit()
        self.inp_tg.setPlaceholderText("Es: @MioCanaleSegnali")
        self.btn_active = QPushButton("ATTIVA QUESTO ROBOT")
        self.btn_active.setCheckable(True)
        self.btn_active.clicked.connect(self.toggle_active)
        
        form.addRow("Nome:", self.inp_name)
        form.addRow("Canale Telegram:", self.inp_tg)
        form.addRow(self.btn_active)
        
        btn_save = QPushButton("Salva Modifiche")
        btn_save.clicked.connect(self.save_robot)
        form.addRow(btn_save)

        layout.addLayout(left_panel, 1)
        layout.addWidget(self.right_panel, 2)
        
        self.refresh_list()

    def refresh_list(self):
        self.list_widget.clear()
        for name in self.robots_data:
            self.list_widget.addItem(name)

    def create_robot(self):
        name = f"Agent_{len(self.robots_data)+1}"
        self.robots_data[name] = {"telegram": "", "active": False}
        self.save_data()
        self.refresh_list()

    def load_robot(self, item, prev):
        if not item: return
        self.right_panel.setVisible(True)
        name = item.text()
        self.current_robot = name
        data = self.robots_data[name]
        
        self.inp_name.setText(name)
        self.inp_tg.setText(data.get("telegram", ""))
        self.update_active_btn(data.get("active", False))

    def save_robot(self):
        if not self.current_robot: return
        # Gestione rinomina
        new_name = self.inp_name.text()
        old_name = self.current_robot
        
        data = self.robots_data[old_name]
        data["telegram"] = self.inp_tg.text()
        
        if new_name != old_name:
            self.robots_data[new_name] = data
            del self.robots_data[old_name]
            self.current_robot = new_name
            
        self.save_data()
        self.refresh_list()
        QMessageBox.information(self, "Salvataggio", "Agente salvato.")

    def update_active_btn(self, active):
        if active:
            self.btn_active.setText("🟢 AGENTE ATTIVO (In Controllo)")
            self.btn_active.setStyleSheet("background-color: #2e7d32; color: white;")
            self.btn_active.setChecked(True)
        else:
            self.btn_active.setText("🔴 AGENTE INATTIVO")
            self.btn_active.setStyleSheet("background-color: #c62828; color: white;")
            self.btn_active.setChecked(False)

    def toggle_active(self):
        # Logica: Solo un robot attivo alla volta (per ora)
        is_active = self.btn_active.isChecked()
        
        # Disattiva tutti gli altri
        for name in self.robots_data:
            self.robots_data[name]["active"] = False
            
        self.robots_data[self.current_robot]["active"] = is_active
        self.update_active_btn(is_active)
        self.save_data()
        
        if is_active and self.controller:
            # 🔥 INIEZIONE LOGICA NEL CORE 🔥
            data = self.robots_data[self.current_robot]
            data["name"] = self.current_robot
            self.controller.load_robot_profile(data)
            QMessageBox.information(self, "Attivazione", f"{self.current_robot} ora controlla il sistema!")


# ============================================================================
#  MAIN WINDOW (ASSEMBLE EVERYTHING)
# ============================================================================
class MainWindow(QMainWindow):
    def __init__(self, vision=None, telegram_learner=None, rpa_healer=None,
                 logger=None, executor=None, config=None, monitor=None,
                 controller=None):
        super().__init__()
        self.controller = controller
        self.setWindowTitle("SuperAgent V5.5 - SENTINEL CONTROL PANEL")
        self.resize(1100, 750)
        self.setStyleSheet(STYLE_SHEET)

        # Setup Logger GUI
        self.logger_engine, self.qt_handler = setup_logger()

        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        # --- CREAZIONE TAB REALI ---
        self.factory = RobotFactoryTab(controller)
        self.supervisor = SupervisorTab(controller, self.factory)
        self.stats_tab = StatsTab(controller)
        self.money_tab = MoneyTab(controller)
        self.trainer_tab = TrainerTab(controller, logger)
        
        # Tab Mapping e Telegram (dal file importato o stub)
        try:
            from ui.mapping_tab import MappingTab
            from ui.telegram_tab import TelegramTab
            self.mapping_tab = MappingTab(controller)
            self.telegram_tab = TelegramTab(controller=controller)
        except ImportError:
            self.mapping_tab = QWidget()
            self.telegram_tab = QWidget()

        # Tab RPA (Passiva)
        self.rpa_tab = QWidget() # Placeholder per RPA Monitor esistente

        # --- AGGIUNTA TAB ORDINE LOGICO ---
        self.tabs.addTab(self.supervisor, "📡 SUPERVISOR")
        self.tabs.addTab(self.factory, "🤖 FACTORY")
        self.tabs.addTab(self.stats_tab, "📊 STATS")
        self.tabs.addTab(self.money_tab, "💰 MONEY")
        self.tabs.addTab(self.telegram_tab, "✈️ TELEGRAM")
        self.tabs.addTab(self.mapping_tab, "🗺️ MAPPING")
        self.tabs.addTab(self.trainer_tab, "🧠 TRAINER")
        
        # Collegamento Log
        if self.qt_handler:
            self.qt_handler.log_signal.connect(self.update_gui_log)

        if self.controller:
            self.controller.training_complete.connect(self.trainer_tab.on_training_complete)

    @Slot(str, str)
    def update_gui_log(self, level, msg):
        if hasattr(self, 'supervisor'):
            color = "#4CAF50" if level == "INFO" else "#F44336" if level in ["ERROR", "CRITICAL"] else "#FFC107"
            self.supervisor.log.append(f"<span style='color:{color}'>[{datetime.now().strftime('%H:%M:%S')}] {msg}</span>")

    # ✅ METODO closeEvent AGGIUNTO PER SHUTDOWN PULITO
    def closeEvent(self, event):
        # 1. Spegnimento Controller (Telegram, Browser, Thread)
        if self.controller:
            self.controller.shutdown()
            
        # 2. Spegnimento Worker RPA (UI)
        if hasattr(self, 'rpa_worker') and self.rpa_worker:
            self.rpa_worker.stop()
            self.rpa_worker.wait(2000)
            
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

# ============================================================================
#  RUN APP
# ============================================================================
def run_app(vision=None, telegram_learner=None, rpa_healer=None,
            logger=None, executor=None, config=None, monitor=None,
            controller=None):
    
    import ctypes
    try: ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except: pass
    
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    try:
        from core.logger import setup_logger
        logger_engine, _ = setup_logger()
    except:
        logger_engine = logging.getLogger("Fallback")

    spy = GlobalSpy(logger_engine)
    app.installEventFilter(spy)

    win = MainWindow(vision, telegram_learner, rpa_healer,
                     logger, executor, config, monitor, controller)
    win.showMaximized()
    return app.exec()
