"""
SuperAgent Desktop App V5.5 - SENTINEL EDITION (DPI AWARE & ELASTIC LAYOUT)
"""
import os
import sys
import re
import time
import queue
import json
import logging
import requests
import ctypes  # Necessario per il fix DPI Windows
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
    QSizePolicy, QScrollArea
)
from PySide6.QtCore import Qt, Signal, QThread, QTimer, Slot, QSize, QObject, QEvent
from PySide6.QtGui import QFont, QColor, QPalette, QTextCursor, QIcon, QScreen

# --- INTEGRAZIONE LOGGER ---
try:
    from core.logger import setup_logger
except ImportError:
    # Fallback se il file core/logger.py non esiste ancora
    def setup_logger():
        return logging.getLogger("Fallback"), None

# Gestione import opzionali per evitare crash immediati se mancano moduli
try:
    from core.money_management import RoserpinaTable
    from ui.mapping_tab import MappingTab
    from ui.telegram_tab import TelegramTab
except ImportError:
    class RoserpinaTable:
        def __init__(self, *args, **kwargs): pass
    class MappingTab(QWidget):
        def __init__(self, *args, **kwargs): super().__init__()
    class TelegramTab(QWidget):
        def __init__(self, **kwargs): super().__init__()


# ============================================================================
#  PATH SYSTEM & LOGGING (EXE COMPATIBLE & ROBUST)
# ============================================================================
def get_project_root():
    """Restituisce la cartella reale dove si trova l'EXE o lo script."""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    try:
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    except Exception:
        return os.getcwd()

_ROOT_DIR = get_project_root()

# Crea la cartella logs se non esiste
LOG_DIR = os.path.join(_ROOT_DIR, "logs")
if not os.path.exists(LOG_DIR):
    try:
        os.makedirs(LOG_DIR)
    except Exception:
        LOG_DIR = _ROOT_DIR 

# File di configurazione e log con percorsi assoluti
ROBOTS_FILE = os.path.join(_ROOT_DIR, "config", "my_robots.json")
API_FILE = os.path.join(_ROOT_DIR, "config", "api_config.json")
LOG_FILE = os.path.join(LOG_DIR, "superagent_v5.log")

# Setup Logger (Console + File)
_logger = logging.getLogger("desktop_app")
if not _logger.handlers:
    try:
        _fh = RotatingFileHandler(
            LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8")
        formatter = logging.Formatter("%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s")
        _fh.setFormatter(formatter)
        _logger.addHandler(_fh)
        
        _ch = logging.StreamHandler()
        _ch.setFormatter(formatter)
        _logger.addHandler(_ch)
        
        _logger.setLevel(logging.INFO)
        _logger.info(f"=== SUPERAGENT STARTED === ROOT: {_ROOT_DIR}")
    except Exception as e:
        print(f"ERRORE CRITICO LOGGER: {e}")


# ============================================================================
#  GLOBAL STYLESHEET
# ============================================================================
STYLE_SHEET = """
QMainWindow, QWidget { background-color: #343541; color: #ececf1; font-family: 'Segoe UI', sans-serif; }
QTabWidget::pane { border: 1px solid #4d4d4f; top: -1px; }
QTabBar::tab { background: #202123; color: #8e8ea0; padding: 10px 20px; border-top-left-radius: 4px; border-top-right-radius: 4px; }
QTabBar::tab:selected { background: #343541; color: white; border-top: 2px solid #10a37f; font-weight: bold; }
QLineEdit {
    background-color: #40414f; color: white; border: 1px solid #565869;
    border-radius: 4px; padding: 8px; selection-background-color: #10a37f;
}
QLineEdit:focus { border: 1px solid #10a37f; background-color: #4d4d4f; }
QLineEdit:disabled { background-color: #2a2b32; color: #666; }
QTextEdit { background-color: #353740; border: none; color: #ececf1; padding: 5px; }
QListWidget { background-color: #202123; border: none; }
QListWidget::item { padding: 12px; border-radius: 4px; color: #ececf1; margin: 2px 5px; }
QListWidget::item:selected { background-color: #343541; border: 1px solid #565869; }
QListWidget::item:hover { background-color: #2a2b32; }
QPushButton {
    background-color: #40414f; color: white; border: 1px solid #565869;
    padding: 8px 16px; border-radius: 4px; font-weight: 600;
}
QPushButton:hover { background-color: #4d4d4f; border-color: #8e8ea0; }
QPushButton:pressed { background-color: #2a2b32; }
QPushButton:disabled { background-color: #2a2b32; color: #555; border: none; }
QTableWidget { gridline-color: #444; background-color: #1e1e1e; }
QHeaderView::section { background-color: #202123; color: white; padding: 5px; border: none; }
QSplitter::handle { background-color: #4d4d4f; }
"""


# ============================================================================
#  CUSTOM INPUT DIALOG
# ============================================================================
class CustomInputDialog(QDialog):
    def __init__(self, title, label_text, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setFixedWidth(400)
        self.setWindowModality(Qt.ApplicationModal)
        self.setStyleSheet("background-color: #202123; color: white;")

        layout = QVBoxLayout(self)
        lbl = QLabel(label_text)
        lbl.setStyleSheet("font-size: 14px; font-weight: bold; margin-bottom: 5px;")
        layout.addWidget(lbl)

        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Scrivi qui...")
        self.input_field.setStyleSheet(
            "QLineEdit { background-color: white; color: black; border: 3px solid #10a37f; padding: 12px; font-size: 16px; font-weight: bold; }"
            "QLineEdit:focus { border-color: #19c37d; }")
        layout.addWidget(self.input_field)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        btns.setStyleSheet(
            "QPushButton { background-color: #10a37f; color: white; border: none; padding: 10px; }"
            "QPushButton[text='Cancel'] { background-color: #555; }")
        layout.addWidget(btns)
        QTimer.singleShot(100, self.input_field.setFocus)

    def get_text(self):
        return self.input_field.text().strip()


# ============================================================================
#  JSON HELPERS
# ============================================================================
def _load_json(path):
    if not os.path.exists(path): return {}
    try:
        with open(path, "r", encoding="utf-8") as f: return json.load(f)
    except Exception as e:
        _logger.error(f"Errore caricamento {path}: {e}")
        return {}

def _save_json(path, data, parent_widget=None):
    try:
        folder = os.path.dirname(path)
        if folder and not os.path.exists(folder): os.makedirs(folder, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f: json.dump(data, f, indent=4)
        return True
    except Exception as e:
        _logger.error(f"Errore scrittura {path}: {e}")
        if parent_widget:
            QMessageBox.critical(parent_widget, "Errore File", f"Non posso salvare in:\n{path}\n\nMotivo: {e}")
        return False

def _ensure_files_exist():
    for path, default in [(ROBOTS_FILE, {}), (API_FILE, {"key": ""})]:
        if not os.path.exists(path): _save_json(path, default)

_ensure_files_exist()


# ============================================================================
#  1. SENTINEL FIREWALL
# ============================================================================
class SafetySentinel:
    FORBIDDEN = ["import os", "sys.exit", "os.system", "rm -rf", "format c:", "shutdown", "wget ", "curl "]
    @staticmethod
    def scan_input(text: str) -> bool:
        text_lower = text.lower()
        for p in SafetySentinel.FORBIDDEN:
            if p in text_lower: return False
        return True
    @staticmethod
    def sanitize_log(text: str) -> str:
        if not text: return ""
        return re.sub(r'(sk-or-[a-zA-Z0-9\-\_]{5,})', r'sk-***HIDDEN***', text)
    @staticmethod
    def warning() -> str: return "BLOCKED BY SENTINEL SECURITY."


# ============================================================================
#  2. OPENROUTER WORKER
# ============================================================================
class OpenRouterWorker(QThread):
    response_received = Signal(str)
    log_received = Signal(str)
    finished_task = Signal(bool)

    def __init__(self, api_key, history, system_prompt):
        super().__init__()
        self.api_key = api_key
        self.history = history[-6:]
        self.system_prompt = system_prompt
        self.fallback_models = [
            "google/gemini-2.0-flash-lite-preview-02-05:free",
            "openai/gpt-oss-120b:free",
            "meta-llama/llama-3.3-70b-instruct:free",
            "qwen/qwen-2.5-coder-32b-instruct:free",
            "deepseek/deepseek-r1:free",
        ]

    def run(self):
        _logger.info("Worker AI avviato.")
        for msg in self.history:
            if not SafetySentinel.scan_input(msg.get("content", "")):
                self.log_received.emit("Sentinel: Input storico infetto.")
                self.response_received.emit(SafetySentinel.warning())
                self.finished_task.emit(False)
                return

        messages = [{"role": "system", "content": self.system_prompt}] + self.history
        session = requests.Session()
        retry = Retry(total=2, backoff_factor=0.5, status_forcelist=[429, 500, 502, 503], allowed_methods=["POST"])
        session.mount("https://", HTTPAdapter(max_retries=retry))
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json", "HTTP-Referer": "https://superagent.app", "X-Title": "SuperAgent V5"}

        success = False
        for model in self.fallback_models:
            self.log_received.emit(f"Connessione a {model}...")
            try:
                payload = {"model": model, "messages": messages, "temperature": 0.7, "max_tokens": 800}
                resp = session.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload, timeout=12)
                if resp.status_code == 200:
                    content = resp.json()['choices'][0]['message']['content']
                    if not SafetySentinel.scan_input(content):
                        self.log_received.emit("Sentinel: Risposta AI bloccata.")
                        self.response_received.emit(SafetySentinel.warning())
                        self.finished_task.emit(False)
                        return
                    self.log_received.emit("Risposta ricevuta.")
                    self.response_received.emit(content)
                    success = True
                    break
                elif resp.status_code == 401:
                    self.log_received.emit("Errore Auth: Controlla la API Key")
                    break
                else:
                    self.log_received.emit(f"Errore HTTP {resp.status_code}")
            except Exception as e:
                self.log_received.emit(SafetySentinel.sanitize_log(str(e))[:60])
            time.sleep(0.3)

        self.finished_task.emit(success)


# ============================================================================
#  3. ROBOT FACTORY (ELASTIC LAYOUT + THREAD SAFETY)
# ============================================================================
class RobotFactoryTab(QWidget):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self.current_robot_name = None
        self.robots_data = _load_json(ROBOTS_FILE)
        self.api_key = _load_json(API_FILE).get("key", "")
        self._is_busy = False  # SEMAFORO THREAD SAFETY
        self.init_ui()

    def init_ui(self):
        # FIX LAYOUT: Usiamo QSplitter per renderlo elastico
        main = QVBoxLayout(self)
        main.setContentsMargins(0, 0, 0, 0)
        
        splitter = QSplitter(Qt.Horizontal)
        main.addWidget(splitter)

        # --- SIDEBAR (Elastica) ---
        side = QWidget()
        side.setMinimumWidth(240)
        side.setMaximumWidth(400)
        side.setStyleSheet("background-color: #202123; border-right: 1px solid #4d4d4f;")
        
        vbox = QVBoxLayout(side)
        vbox.setContentsMargins(10, 20, 10, 20)
        vbox.setSpacing(15)

        lbl_title = QLabel("FLOTTA AGENTI")
        lbl_title.setStyleSheet("color:#8e8ea0; font-weight:bold; font-size:12px; letter-spacing:1px;")
        vbox.addWidget(lbl_title)

        btn_new = QPushButton("+ NUOVO AGENTE")
        btn_new.setMinimumHeight(40)
        btn_new.setStyleSheet("background-color: #10a37f; color: white; border: none; padding: 10px; font-weight: bold;")
        btn_new.clicked.connect(self.create_robot)
        vbox.addWidget(btn_new)

        self.list = QListWidget()
        self.list.currentItemChanged.connect(self.load_robot)
        vbox.addWidget(self.list)

        api_box = QGroupBox("Configurazione API")
        api_box.setStyleSheet("border: 1px solid #444; padding: 10px; margin-top: 10px;")
        ab_lay = QVBoxLayout(api_box)
        self.txt_api = QLineEdit(self.api_key)
        self.txt_api.setPlaceholderText("sk-or-...")
        self.txt_api.setEchoMode(QLineEdit.Password)
        self.txt_api.textChanged.connect(self.save_api)
        ab_lay.addWidget(self.txt_api)
        vbox.addWidget(api_box)
        
        splitter.addWidget(side)

        # --- CHAT PANEL ---
        self.panel = QWidget()
        self.panel.setVisible(False)
        p_lay = QVBoxLayout(self.panel)
        p_lay.setContentsMargins(0, 0, 0, 0)
        p_lay.setSpacing(0)

        # Header
        head = QFrame()
        head.setStyleSheet("background-color: #343541; border-bottom: 1px solid #2d2d30; padding: 15px;")
        h_box = QHBoxLayout(head)
        self.lbl_name = QLabel("Robot")
        self.lbl_name.setStyleSheet("font-size: 20px; font-weight: bold; color: #10a37f;")

        self.txt_tg = QLineEdit()
        self.txt_tg.setPlaceholderText("@UsernameCanale")
        self.txt_tg.setFixedWidth(200)
        self.txt_tg.setStyleSheet("background: #40414f; color: #10a37f; font-weight: bold; padding: 8px;")
        self.txt_tg.textChanged.connect(self.save_config)

        self.btn_act = QPushButton("AVVIA")
        self.btn_act.setCheckable(True)
        self.btn_act.setFixedWidth(80)
        self.btn_act.clicked.connect(self.toggle_active)

        self.btn_del = QPushButton("X")
        self.btn_del.setFixedWidth(40)
        self.btn_del.setStyleSheet("background: #ef4444; border:none;")
        self.btn_del.clicked.connect(self.delete_robot)

        h_box.addWidget(self.lbl_name)
        h_box.addStretch()
        h_box.addWidget(QLabel("Target:"))
        h_box.addWidget(self.txt_tg)
        h_box.addWidget(self.btn_act)
        h_box.addWidget(self.btn_del)
        p_lay.addWidget(head)

        # Chat
        self.chat = QTextEdit()
        self.chat.setReadOnly(True)
        p_lay.addWidget(self.chat)

        # Input
        in_box = QFrame()
        in_box.setStyleSheet("background-color: #343541; padding: 20px; border-top: 1px solid #444;")
        ib_lay = QHBoxLayout(in_box)

        self.inp = QLineEdit()
        self.inp.setPlaceholderText("Istruzioni...")
        self.inp.setMinimumHeight(40)
        self.inp.setStyleSheet("background: #40414f; color: white; border: 1px solid #565869; border-radius: 6px; padding: 10px;")
        self.inp.returnPressed.connect(self.send_msg)

        self.btn_send = QPushButton("Invia")
        self.btn_send.setMinimumHeight(40)
        self.btn_send.setStyleSheet("background-color: #19c37d; color: white; font-weight: bold; border-radius: 6px;")
        self.btn_send.clicked.connect(self.send_msg)

        ib_lay.addWidget(self.inp)
        ib_lay.addWidget(self.btn_send)
        p_lay.addWidget(in_box)
        
        splitter.addWidget(self.panel)
        splitter.setStretchFactor(1, 1)

        self.refresh_list()

    def save_data(self): _save_json(ROBOTS_FILE, self.robots_data, self)
    def save_api(self):
        self.api_key = self.txt_api.text().strip()
        _save_json(API_FILE, {"key": self.api_key}, self)

    def refresh_list(self):
        self.list.clear()
        for name, data in self.robots_data.items():
            icon = "[ON]" if data.get("active", False) else "[OFF]"
            self.list.addItem(f"{icon} {name}")

    def create_robot(self):
        if self._is_busy: return
        dlg = CustomInputDialog("Nuovo Agente", "Nome del Robot:", self)
        if dlg.exec():
            name = dlg.get_text()
            if name and name not in self.robots_data:
                self.robots_data[name] = {"active": False, "telegram": "", "history": []}
                self.save_data()
                self.refresh_list()
            elif name in self.robots_data:
                QMessageBox.warning(self, "Errore", "Nome esistente.")

    def load_robot(self, cur, prev):
        if not cur:
            self.panel.setVisible(False)
            return
        name = cur.text().replace("[ON] ", "").replace("[OFF] ", "")
        self.current_robot_name = name
        data = self.robots_data[name]
        self.panel.setVisible(True)
        self.lbl_name.setText(name)
        self.txt_tg.blockSignals(True)
        self.txt_tg.setText(data.get("telegram", ""))
        self.txt_tg.blockSignals(False)
        self.update_btn(data.get("active", False))
        self.chat.clear()
        for m in data.get("history", []):
            self.append_visual(m["role"], m["content"])
        self.inp.setFocus()

    def save_config(self):
        if self.current_robot_name in self.robots_data:
            self.robots_data[self.current_robot_name]["telegram"] = self.txt_tg.text()
            self.save_data()

    def toggle_active(self):
        n = self.current_robot_name
        if not n: return
        self.robots_data[n]["active"] = not self.robots_data[n].get("active", False)
        self.save_data()
        self.refresh_list()
        self.update_btn(self.robots_data[n]["active"])

    def update_btn(self, active):
        if active:
            self.btn_act.setText("PAUSA")
            self.btn_act.setStyleSheet("background:#eab308; color:black; border:none; border-radius:4px; font-weight:bold;")
        else:
            self.btn_act.setText("AVVIA")
            self.btn_act.setStyleSheet("background:#22c55e; color:white; border:none; border-radius:4px; font-weight:bold;")

    def delete_robot(self):
        name = self.current_robot_name
        if not name: return
        if QMessageBox.question(self, "Elimina", f"Cancellare {name}?", QMessageBox.Yes|QMessageBox.No) == QMessageBox.Yes:
            del self.robots_data[name]
            self.current_robot_name = None
            self.save_data()
            self.panel.setVisible(False)
            self.refresh_list()

    def set_busy(self, busy):
        self._is_busy = busy
        self.inp.setEnabled(not busy)
        self.btn_send.setEnabled(not busy)
        self.btn_send.setText("..." if busy else "Invia")

    def send_msg(self):
        if self._is_busy: return
        txt = self.inp.text().strip()
        if not txt: return
        if not SafetySentinel.scan_input(txt):
            self.append_visual("system", "BLOCKED BY SENTINEL")
            self.inp.clear()
            return
        if len(self.api_key) < 5:
            QMessageBox.critical(self, "Errore", "Manca API Key!")
            return

        name = self.current_robot_name
        self.set_busy(True)
        self.append_visual("user", txt)
        self.robots_data[name]["history"].append({"role": "user", "content": txt})
        self.save_data()
        self.inp.clear()

        sys_p = f"Sei {name}. Telegram target: {self.robots_data[name].get('telegram', '')}."
        self.worker = OpenRouterWorker(self.api_key, self.robots_data[name]["history"], sys_p)
        self.worker.response_received.connect(self.on_resp)
        self.worker.log_received.connect(self.on_log)
        self.worker.finished_task.connect(self.on_task_end)
        self.worker.start()

    def on_log(self, txt):
        self.chat.append(f"<div style='color:#666; font-size:10px;'>{txt}</div>")
        self.chat.moveCursor(QTextCursor.End)

    def on_resp(self, txt):
        name = self.current_robot_name
        self.append_visual("assistant", txt)
        if name in self.robots_data:
            self.robots_data[name]["history"].append({"role": "assistant", "content": txt})
            self.save_data()

    def on_task_end(self, success):
        self.set_busy(False)
        name = self.current_robot_name
        mw = self.window()
        if name and hasattr(mw, "supervisor"):
            mw.supervisor.report(name, success)

    def append_visual(self, role, txt):
        if role == "user":
            html = f"<div style='text-align:right; margin:5px;'><span style='background:#10a37f; color:white; padding:8px 12px; border-radius:15px;'>{txt}</span></div>"
        elif role == "assistant":
            html = f"<div style='text-align:left; margin:5px;'><span style='background:#444654; color:#ececf1; padding:8px 12px; border-radius:15px;'>{txt}</span></div>"
        else:
            html = f"<div style='text-align:center; color:#888; margin:5px;'><i>{txt}</i></div>"
        self.chat.append(html)
        self.chat.moveCursor(QTextCursor.End)


# ============================================================================
#  4. SUPERVISOR
# ============================================================================
class SupervisorTab(QWidget):
    def __init__(self, controller, factory):
        super().__init__()
        self.controller = controller
        self.factory = factory
        self.stats = {}
        self.timer = QTimer()
        self.timer.timeout.connect(self.scan)
        self.timer.start(2000)
        self.init_ui()

    def init_ui(self):
        lay = QVBoxLayout(self)
        h = QFrame()
        h.setStyleSheet("background:#202123; padding:15px; border-radius:6px;")
        hl = QHBoxLayout(h)
        lbl = QLabel("SUPERVISOR ACTIVE")
        lbl.setStyleSheet("color:#10a37f; font-weight:bold; font-size:16px;")
        btn_kill = QPushButton("EMERGENCY STOP")
        btn_kill.setStyleSheet("background:#ef4444; border:none;")
        btn_kill.clicked.connect(self.kill_all)
        hl.addWidget(lbl)
        hl.addStretch()
        hl.addWidget(btn_kill)
        lay.addWidget(h)

        self.tab = QTableWidget(0, 5)
        self.tab.setHorizontalHeaderLabels(["AGENTE", "STATO", "ERR", "REQ", "HEALTH"])
        self.tab.horizontalHeader().setStretchLastSection(True)
        self.tab.setStyleSheet("border:none; background:#202123; color:#ddd;")
        lay.addWidget(self.tab)

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(200)
        self.log.setStyleSheet("background:black; color:#10a37f; font-family:monospace; padding:5px;")
        lay.addWidget(self.log)

    def scan(self):
        d = self.factory.robots_data
        self.tab.setRowCount(len(d))
        for i, (name, data) in enumerate(d.items()):
            if name not in self.stats: self.stats[name] = {"err": 0, "req": 0}
            st = self.stats[name]
            act = data.get("active", False)
            health = "OK"
            if st["err"] > 5:
                health = "KILLED (Errors)"
                self.force_stop(name, "Troppi errori")
            elif st["req"] > 50:
                health = "PAUSED (Spam)"
                self.force_stop(name, "Troppe richieste")
            ico = "RUNNING" if act else "SLEEPING"
            if health != "OK": ico = "CRITICAL"
            self.tab.setItem(i, 0, QTableWidgetItem(name))
            self.tab.setItem(i, 1, QTableWidgetItem(ico))
            self.tab.setItem(i, 2, QTableWidgetItem(str(st["err"])))
            self.tab.setItem(i, 3, QTableWidgetItem(str(st["req"])))
            self.tab.setItem(i, 4, QTableWidgetItem(health))

    def report(self, name, success):
        if not name in self.stats: return
        self.stats[name]["req"] += 1
        if not success: self.stats[name]["err"] += 1
        else: self.stats[name]["err"] = max(0, self.stats[name]["err"] - 1)

    def force_stop(self, name, reason):
        if self.factory.robots_data.get(name, {}).get("active"):
            self.factory.robots_data[name]["active"] = False
            self.factory.save_data()
            self.factory.refresh_list()
            self.log.append(f"STOPPED {name}: {reason}")

    def kill_all(self):
        if QMessageBox.question(self, "STOP", "Fermare TUTTI?", QMessageBox.Yes|QMessageBox.No) == QMessageBox.Yes:
            for n in self.factory.robots_data: self.factory.robots_data[n]["active"] = False
            self.factory.save_data()
            self.factory.refresh_list()
            self.log.append("SYSTEM HALT.")


# ============================================================================
#  RPA / WORKER UTILS
# ============================================================================
class RPAWorker(QThread):
    bet_placed = Signal(dict)
    bet_error = Signal(str)
    def __init__(self, executor, logger=None, monitor=None, controller=None):
        super().__init__()
        self._queue = queue.Queue()
        self._running = True
        self.executor = executor
        self.controller = controller
    def enqueue_bet(self, signal_data): self._queue.put(signal_data)
    def stop(self):
        self._running = False
        self._queue.put(None)
    def run(self):
        while self._running:
            item = self._queue.get()
            if item is None: break
            try:
                if self.controller:
                    res = self.controller.handle_signal(item)
                    item["placed"] = res
                    item["timestamp"] = datetime.now().isoformat()
                    if res: self.bet_placed.emit(item)
                    else: self.bet_error.emit(f"Failed: {item.get('teams')}")
            except Exception as e: self.bet_error.emit(str(e))

class RPAMonitorTab(QWidget):
    def __init__(self, executor=None, rpa_worker=None, logger=None, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("RPA Monitor"))
        self.bet_table = QTableWidget(0, 4)
        layout.addWidget(self.bet_table)
        if rpa_worker: rpa_worker.bet_placed.connect(self._on_bet_placed)
    def _on_bet_placed(self, data):
        r = self.bet_table.rowCount()
        self.bet_table.insertRow(r)
        self.bet_table.setItem(r, 0, QTableWidgetItem(str(data.get("teams"))))


# ============================================================================
#  SETTINGS / MONEY / STATS
# ============================================================================
class SettingsTab(QWidget):
    stealth_changed = Signal(str)
    def __init__(self, config=None, logger=None, controller=None, parent=None):
        super().__init__(parent)
        self.controller = controller
        main_layout = QVBoxLayout(self)
        
        # Scroll area per schermi piccoli
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        content = QWidget()
        layout = QVBoxLayout(content)
        
        layout.addWidget(QLabel("Stealth Mode"))
        self.stealth_combo = QComboBox()
        self.stealth_combo.addItems(["Umano Lento", "Bilanciato", "Pro"])
        
        default_mode = (config or {}).get("rpa", {}).get("stealth_mode", "balanced")
        mode_map = {"slow": 0, "balanced": 1, "pro": 2}
        self.stealth_combo.setCurrentIndex(mode_map.get(default_mode, 1))
        layout.addWidget(self.stealth_combo)
        
        self.stealth_combo.currentIndexChanged.connect(lambda i: self.stealth_changed.emit(["slow", "balanced", "pro"][i]))
        
        layout.addStretch()
        scroll.setWidget(content)
        main_layout.addWidget(scroll)

class MoneyTab(QWidget):
    def __init__(self, controller=None):
        super().__init__()
        self.controller = controller
        layout = QFormLayout(self)
        self.bankroll = QDoubleSpinBox()
        self.bankroll.setValue(100)
        layout.addRow("Bankroll", self.bankroll)
        btn = QPushButton("Save")
        btn.clicked.connect(lambda: setattr(controller, 'table', RoserpinaTable(self.bankroll.value(), 3.0)) if controller else None)
        layout.addRow(btn)

class StatsTab(QWidget):
    def __init__(self):
        super().__init__()
        QVBoxLayout(self).addWidget(QLabel("Statistics Placeholder"))

class TrainerTab(QWidget):
    def __init__(self, controller=None, logger=None, parent=None):
        super().__init__(parent)
        self.controller = controller
        self._is_busy = False # Semaforo locale
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("AI Trainer"))
        self.chat_display = QTextEdit()
        layout.addWidget(self.chat_display)
        self.train_btn = QPushButton("Train Step")
        self.train_btn.clicked.connect(self._on_train_step)
        layout.addWidget(self.train_btn)

    def _on_train_step(self):
        if self._is_busy: return
        if self.controller:
            self._is_busy = True
            self.train_btn.setEnabled(False)
            self.train_btn.setText("Training...")
            self.controller.request_training()

    @Slot(str)
    def on_training_complete(self, res):
        self._is_busy = False
        self.train_btn.setEnabled(True)
        self.train_btn.setText("Train Step")
        self.chat_display.append(f"Result: {res}")


# ============================================================================
#  MAIN WINDOW
# ============================================================================
class MainWindow(QMainWindow):
    def __init__(self, vision=None, telegram_learner=None, rpa_healer=None,
                 logger=None, executor=None, config=None, monitor=None,
                 controller=None):
        super().__init__()
        self.controller = controller
        self.setWindowTitle("SuperAgent V5.5 Sentinel")
        
        # 1. Dimensionamento intelligente
        self.setMinimumSize(800, 600) # Minimo sindacale per non rompere layout
        self.setStyleSheet(STYLE_SHEET)

        self.rpa_worker = None
        if executor or controller:
            self.rpa_worker = RPAWorker(executor, logger, monitor, controller)
            self.rpa_worker.start()

        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        # Tabs
        self.factory = RobotFactoryTab(controller)
        self.supervisor = SupervisorTab(controller, self.factory)
        
        # --- LOGGER SETUP & CONNECTION ---
        self.logger_engine, self.qt_handler = setup_logger()
        if self.qt_handler:
            self.qt_handler.log_signal.connect(self.update_gui_log)
        
        self.tabs.addTab(self.factory, "Factory")
        self.tabs.addTab(self.supervisor, "SUPERVISOR")
        self.rpa_tab = RPAMonitorTab(executor, self.rpa_worker, logger)
        self.tabs.addTab(self.rpa_tab, "RPA Monitor")
        self.settings_tab = SettingsTab(config, logger, controller)
        self.settings_tab.stealth_changed.connect(self._on_stealth_changed)
        self.tabs.addTab(self.settings_tab, "Settings")
        
        if self.controller:
            self.money_tab = MoneyTab(self.controller)
            self.tabs.addTab(self.money_tab, "Roserpina")
            self.mapping_tab = MappingTab(self.controller)
            self.tabs.addTab(self.mapping_tab, "Auto-Mapping")

        self.telegram_tab = TelegramTab(agent=vision)
        self.tabs.addTab(self.telegram_tab, "Telegram")
        self.stats_tab = StatsTab()
        self.tabs.addTab(self.stats_tab, "Stats")
        self.trainer_tab = TrainerTab(controller, logger)
        self.tabs.addTab(self.trainer_tab, "Trainer")

        if self.controller:
            self.controller.training_complete.connect(self.trainer_tab.on_training_complete)
        
        # Log di avvio nella GUI
        self.logger_engine.info("Sistema avviato correttamente.")

    @Slot(str, str)
    def update_gui_log(self, level, msg):
        """Riceve i log da qualsiasi thread e li mostra nel Supervisor"""
        if not hasattr(self, 'supervisor') or not self.supervisor:
            return
            
        color = "#10a37f" # Verde default
        if level in ["ERROR", "CRITICAL"]:
            color = "#ef4444" # Rosso
        elif level == "WARNING":
            color = "#eab308" # Giallo/Arancio
        
        html = f"<div style='color:{color}; margin-bottom:2px;'><span style='color:#666;'>[{datetime.now().strftime('%H:%M:%S')}]</span> <b>{level}:</b> {msg}</div>"
        
        self.supervisor.log.append(html)
        # Scroll automatico
        scrollbar = self.supervisor.log.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def closeEvent(self, event):
        if self.rpa_worker:
            self.rpa_worker.stop()
            self.rpa_worker.wait(2000)
        super().closeEvent(event)

    @Slot(str)
    def _on_stealth_changed(self, mode):
        if self.controller: self.controller.set_stealth_mode(mode)


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


# ============================================================================
#  GLOBAL SPY (LOG DI OGNI CLICK)
# ============================================================================
class GlobalSpy(QObject):
    """Intercetta ogni click e tasto nell'applicazione per i log"""
    def __init__(self, logger):
        super().__init__()
        self.logger = logger

    def eventFilter(self, obj, event):
        # Intercetta Click del Mouse
        if event.type() == QEvent.MouseButtonPress:
            try:
                # Cerca di capire cosa è stato cliccato
                widget_name = obj.objectName() or obj.metaObject().className()
                text = ""
                if hasattr(obj, "text") and callable(obj.text):
                    text = f" ('{obj.text()}')"
                
                self.logger.info(f"🖱️ CLICK UTENTE su: {widget_name}{text}")
            except:
                pass # Non bloccare l'app se il log fallisce
        
        # Intercetta Pressione Tasti (es. Invio)
        elif event.type() == QEvent.KeyPress:
            if event.key() == Qt.Key_Return or event.key() == Qt.Key_Enter:
                self.logger.info("⌨️ TASTO INVIO PREMUTO")
            elif event.key() == Qt.Key_Escape:
                self.logger.info("⌨️ TASTO ESC PREMUTO")

        # Lascia passare l'evento (altrimenti l'app si blocca)
        return super().eventFilter(obj, event)


# ============================================================================
#  RUN APP
# ============================================================================
def run_app(vision=None, telegram_learner=None, rpa_healer=None,
            logger=None, executor=None, config=None, monitor=None,
            controller=None):
    
    # --- 1️⃣ FIX DPI SCALING (CRUCIALE PER WINDOWS) ---
    import os
    import ctypes
    
    # Forza Qt a usare lo scaling del sistema
    os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "1"
    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
    os.environ["QT_SCALE_FACTOR"] = "1"

    # Hack Windows per dire "Sono DPI Aware, non stretchare la finestra"
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2) # 2 = PROCESS_PER_MONITOR_DPI_AWARE
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass
    # -------------------------------------------------
    
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    apply_dark_theme(app)
    
    # --- SETUP LOGGER DI AVVIO ---
    try:
        from core.logger import setup_logger
        logger_engine, _ = setup_logger()
    except:
        logger_engine = logging.getLogger("Fallback")

    # --- 🕵️ INSTALLAZIONE SPIA GLOBALE ---
    spy = GlobalSpy(logger_engine)
    app.installEventFilter(spy)
    # -------------------------------------
    
    if config is None:
        config_path = os.path.join(_ROOT_DIR, "config", "config.yaml")
        if os.path.exists(config_path):
            import yaml
            with open(config_path, "r") as f: config = yaml.safe_load(f)
        else: config = {}

    win = MainWindow(vision, telegram_learner, rpa_healer,
                     logger, executor, config, monitor, controller)
    
    # --- 2️⃣ FIX AVVIO MASSIMIZZATO ---
    win.showMaximized() 
    
    return app.exec()
