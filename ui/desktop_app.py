"""
SuperAgent Desktop App V5.1 - SENTINEL EDITION
"""
import os
import sys
import re
import time
import queue
import json
import requests
from datetime import datetime
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QPushButton, QLabel, QLineEdit, QGroupBox, QTabWidget,
    QTableWidget, QTableWidgetItem, QCheckBox, QMessageBox, QSpinBox,
    QProgressBar, QComboBox, QFormLayout, QSplitter, QDoubleSpinBox,
    QListWidget, QListWidgetItem, QFrame, QInputDialog
)
from PySide6.QtCore import Qt, Signal, QThread, QTimer, Slot
from PySide6.QtGui import QFont, QColor, QPalette, QTextCursor, QIcon

try:
    from core.money_management import RoserpinaTable
    from ui.mapping_tab import MappingTab
    from ui.telegram_tab import TelegramTab
except ImportError:
    class RoserpinaTable:
        def __init__(self, bankroll, target_pct): pass
    class MappingTab(QWidget):
        def __init__(self, controller): super().__init__()
    class TelegramTab(QWidget):
        signal_received = Signal(dict)
        def __init__(self, **kwargs): super().__init__()

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ============================================================================
#  1. SENTINEL FIREWALL
# ============================================================================
class SafetySentinel:
    FORBIDDEN = [
        "import os", "sys.exit", "os.system", "rm -rf", "format c:",
        "drop table", "alter user", "shutdown", "reboot", "wget ", "curl "
    ]

    @staticmethod
    def scan_input(text: str) -> bool:
        text_lower = text.lower()
        for p in SafetySentinel.FORBIDDEN:
            if p in text_lower:
                return False
        return True

    @staticmethod
    def sanitize_log(text: str) -> str:
        if not text:
            return ""
        return re.sub(r'(sk-or-[a-zA-Z0-9\-\_]{5,})', r'sk-***HIDDEN***', text)

    @staticmethod
    def warning() -> str:
        return "SECURITY ALERT: Comando bloccato dal Sentinel System."


# ============================================================================
#  2. OPENROUTER WORKER (RETRY + FALLBACK + SENTINEL)
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
        for msg in self.history:
            if not SafetySentinel.scan_input(msg.get("content", "")):
                self.log_received.emit("Sentinel: Input storico infetto.")
                self.response_received.emit(SafetySentinel.warning())
                self.finished_task.emit(False)
                return

        messages = [{"role": "system", "content": self.system_prompt}] + self.history

        session = requests.Session()
        retry = Retry(total=2, backoff_factor=0.5,
                      status_forcelist=[429, 500, 502, 503],
                      allowed_methods=["POST"])
        session.mount("https://", HTTPAdapter(max_retries=retry))

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://superagent.app",
            "X-Title": "SuperAgent V5"
        }

        success = False
        for model in self.fallback_models:
            self.log_received.emit(f"Connessione a {model}...")
            try:
                payload = {"model": model, "messages": messages,
                           "temperature": 0.7, "max_tokens": 800}
                resp = session.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers=headers, json=payload, timeout=12)

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
            except requests.exceptions.Timeout:
                self.log_received.emit(f"Timeout su {model}")
            except requests.exceptions.ConnectionError:
                self.log_received.emit(f"Connessione fallita su {model}")
            except Exception as e:
                self.log_received.emit(SafetySentinel.sanitize_log(str(e))[:60])
            time.sleep(0.3)

        if not success:
            self.response_received.emit("Tutti i server fallback hanno fallito.")
            self.finished_task.emit(False)
        else:
            self.finished_task.emit(True)



# ============================================================================
#  3. ROBOT FACTORY (MULTI-AGENT UI)
# ============================================================================
class RobotFactoryTab(QWidget):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self.robots_file = "my_robots.json"
        self.api_file = "api_config.json"
        self.current_robot_name = None
        self.robots_data = self.load_data()
        self.api_key = self.load_api_key()
        self.init_ui()

    def init_ui(self):
        main = QHBoxLayout(self)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)

        # SIDEBAR
        side = QWidget()
        side.setFixedWidth(260)
        side.setStyleSheet("background:#202123; border-right:1px solid #444;")
        vbox = QVBoxLayout(side)
        lbl_title = QLabel("FLOTTA AGENTI")
        lbl_title.setStyleSheet("color:#ddd; font-weight:bold; padding:10px;")
        vbox.addWidget(lbl_title)

        btn_new = QPushButton("+ Nuovo Agente")
        btn_new.setStyleSheet(
            "background:transparent; border:1px solid #555; color:white; "
            "padding:8px; text-align:left;")
        btn_new.clicked.connect(self.create_robot)
        vbox.addWidget(btn_new)

        self.list = QListWidget()
        self.list.setStyleSheet("background:transparent; border:none; color:#ddd;")
        self.list.currentItemChanged.connect(self.load_robot)
        vbox.addWidget(self.list)

        vbox.addStretch()
        lbl_api = QLabel("API Key OpenRouter")
        lbl_api.setStyleSheet("color:#888; font-size:11px; font-weight:bold;")
        vbox.addWidget(lbl_api)
        self.txt_api = QLineEdit(self.api_key)
        self.txt_api.setEchoMode(QLineEdit.Password)
        self.txt_api.setStyleSheet("background:#333; color:white; border:1px solid #555; padding:5px;")
        self.txt_api.textChanged.connect(self.save_api)
        vbox.addWidget(self.txt_api)
        main.addWidget(side)

        # CHAT PANEL
        self.panel = QWidget()
        self.panel.setVisible(False)
        self.panel.setStyleSheet("background:#343541;")
        p_lay = QVBoxLayout(self.panel)
        p_lay.setContentsMargins(0, 0, 0, 0)

        # Header
        head = QFrame()
        head.setStyleSheet("background:#202123; padding:10px; border-bottom:1px solid #444;")
        h_box = QHBoxLayout(head)
        self.lbl_name = QLabel("Robot")
        self.lbl_name.setStyleSheet("font-size:18px; font-weight:bold; color:white;")
        self.txt_tg = QLineEdit()
        self.txt_tg.setPlaceholderText("Target Telegram...")
        self.txt_tg.setFixedWidth(200)
        self.txt_tg.setStyleSheet("background:#444; color:white; border:none; padding:5px;")
        self.txt_tg.textChanged.connect(self.save_config)

        self.btn_act = QPushButton("AVVIA")
        self.btn_act.setCheckable(True)
        self.btn_act.setFixedWidth(80)
        self.btn_act.clicked.connect(self.toggle_active)

        self.btn_del = QPushButton("X")
        self.btn_del.setFixedWidth(40)
        self.btn_del.setStyleSheet("background:#a00;")
        self.btn_del.clicked.connect(self.delete_robot)

        h_box.addWidget(self.lbl_name)
        h_box.addStretch()
        h_box.addWidget(QLabel("Target:"))
        h_box.addWidget(self.txt_tg)
        h_box.addWidget(self.btn_act)
        h_box.addWidget(self.btn_del)
        p_lay.addWidget(head)

        # Chat display
        self.chat = QTextEdit()
        self.chat.setReadOnly(True)
        self.chat.setStyleSheet(
            "border:none; padding:15px; color:#ddd; font-size:14px; background:#343541;")
        p_lay.addWidget(self.chat)

        # Input bar
        in_box = QWidget()
        in_box.setStyleSheet("padding:15px;")
        ib_lay = QHBoxLayout(in_box)
        self.inp = QLineEdit()
        self.inp.setPlaceholderText("Scrivi istruzioni...")
        self.inp.setStyleSheet(
            "background:#40414f; color:white; border:1px solid #555; "
            "padding:10px; border-radius:5px;")
        self.inp.returnPressed.connect(self.send_msg)
        self.btn_send = QPushButton("Invia")
        self.btn_send.setStyleSheet(
            "background:#19c37d; color:white; padding:10px; "
            "font-weight:bold; border-radius:5px;")
        self.btn_send.clicked.connect(self.send_msg)
        ib_lay.addWidget(self.inp)
        ib_lay.addWidget(self.btn_send)
        p_lay.addWidget(in_box)

        main.addWidget(self.panel)
        self.refresh_list()

    # --- Data ---
    def load_data(self):
        try:
            with open(self.robots_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def save_data(self):
        with open(self.robots_file, "w", encoding="utf-8") as f:
            json.dump(self.robots_data, f, indent=4)

    def load_api_key(self):
        try:
            with open(self.api_file, "r") as f:
                return json.load(f).get("key", "")
        except Exception:
            return ""

    def save_api(self):
        self.api_key = self.txt_api.text().strip()
        with open(self.api_file, "w") as f:
            json.dump({"key": self.api_key}, f)

    # --- Robot management ---
    def refresh_list(self):
        self.list.clear()
        for name, data in self.robots_data.items():
            icon = "[ON]" if data.get("active", False) else "[OFF]"
            self.list.addItem(f"{icon} {name}")

    def create_robot(self):
        name, ok = QInputDialog.getText(self, "Nuovo Robot", "Nome:")
        if ok and name and name not in self.robots_data:
            self.robots_data[name] = {"active": False, "telegram": "", "history": []}
            self.save_data()
            self.refresh_list()

    def load_robot(self, cur, prev):
        if not cur:
            self.panel.setVisible(False)
            return
        name = cur.text().replace("[ON] ", "").replace("[OFF] ", "")
        self.current_robot_name = name
        data = self.robots_data[name]
        self.panel.setVisible(True)
        self.lbl_name.setText(name)
        self.txt_tg.setText(data.get("telegram", ""))
        self.update_btn(data.get("active", False))
        self.chat.clear()
        for m in data.get("history", []):
            self.append_visual(m["role"], m["content"])

    def save_config(self):
        if self.current_robot_name and self.current_robot_name in self.robots_data:
            self.robots_data[self.current_robot_name]["telegram"] = self.txt_tg.text()
            self.save_data()

    def toggle_active(self):
        n = self.current_robot_name
        if not n or n not in self.robots_data:
            return
        self.robots_data[n]["active"] = not self.robots_data[n].get("active", False)
        self.save_data()
        self.refresh_list()
        self.update_btn(self.robots_data[n]["active"])

    def update_btn(self, active):
        if active:
            self.btn_act.setText("PAUSA")
            self.btn_act.setStyleSheet(
                "background:#eab308; color:black; font-weight:bold;")
        else:
            self.btn_act.setText("AVVIA")
            self.btn_act.setStyleSheet(
                "background:#22c55e; color:white; font-weight:bold;")

    def delete_robot(self):
        name = self.current_robot_name
        if not name or name not in self.robots_data:
            return
        confirm = QMessageBox.question(
            self, "Elimina", f"Cancellare {name}?",
            QMessageBox.Yes | QMessageBox.No)
        if confirm == QMessageBox.Yes:
            del self.robots_data[name]
            self.current_robot_name = None
            self.save_data()
            self.panel.setVisible(False)
            self.refresh_list()

    # --- Chat ---
    def set_busy(self, busy):
        self.inp.setEnabled(not busy)
        self.btn_send.setEnabled(not busy)
        self.btn_send.setText("..." if busy else "Invia")

    def send_msg(self):
        txt = self.inp.text().strip()
        if not txt:
            return
        if not SafetySentinel.scan_input(txt):
            self.append_visual("system", "BLOCKED BY SENTINEL")
            self.inp.clear()
            return
        if len(self.api_key) < 5:
            QMessageBox.critical(self, "Errore", "Manca API Key!")
            return

        name = self.current_robot_name
        if not name or name not in self.robots_data:
            return
        self.set_busy(True)
        self.append_visual("user", txt)
        self.robots_data[name]["history"].append({"role": "user", "content": txt})
        self.save_data()
        self.inp.clear()

        sys_p = f"Sei {name}, assistente betting. Telegram: {self.robots_data[name].get('telegram', '')}."
        self.worker = OpenRouterWorker(self.api_key, self.robots_data[name]["history"], sys_p)
        self.worker.response_received.connect(self.on_resp)
        self.worker.log_received.connect(self.on_log)
        self.worker.finished_task.connect(self.on_task_end)
        self.worker.start()

    def on_log(self, txt):
        self.chat.append(
            f"<div style='color:#888; font-size:10px;'>{txt}</div>")
        self.chat.moveCursor(QTextCursor.End)

    def on_resp(self, txt):
        name = self.current_robot_name
        self.append_visual("assistant", txt)
        if name and name in self.robots_data:
            self.robots_data[name]["history"].append(
                {"role": "assistant", "content": txt})
            self.save_data()

    def on_task_end(self, success):
        self.set_busy(False)
        name = self.current_robot_name
        mw = self.window()
        if name and hasattr(mw, "supervisor"):
            mw.supervisor.report(name, success)

    def append_visual(self, role, txt):
        if role == "system":
            col, who = "#f00", "SYSTEM"
        elif role == "user":
            col, who = "#a8b1ff", "TU"
        else:
            col, who = "#19c37d", "ROBOT"
        self.chat.append(
            f"<div style='margin-bottom:10px;'>"
            f"<b style='color:{col};'>{who}</b><br>"
            f"<span style='color:#ddd;'>{txt}</span></div>")
        self.chat.moveCursor(QTextCursor.End)



# ============================================================================
#  4. SUPERVISOR WATCHDOG (MONITOR & KILL SWITCH)
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

        # Header
        h = QFrame()
        h.setStyleSheet("background:#222; padding:10px; border-radius:5px;")
        hl = QHBoxLayout(h)
        lbl = QLabel("SUPERVISOR ACTIVE")
        lbl.setStyleSheet("color:#0f0; font-weight:bold;")
        btn_kill = QPushButton("EMERGENCY STOP")
        btn_kill.setStyleSheet(
            "background:red; color:white; font-weight:bold; padding:10px;")
        btn_kill.clicked.connect(self.kill_all)
        hl.addWidget(lbl)
        hl.addStretch()
        hl.addWidget(btn_kill)
        lay.addWidget(h)

        # Table
        self.tab = QTableWidget(0, 5)
        self.tab.setHorizontalHeaderLabels(
            ["AGENTE", "STATO", "ERRORI", "REQ", "HEALTH"])
        self.tab.horizontalHeader().setStretchLastSection(True)
        self.tab.setStyleSheet("background:#111; color:white; border:none;")
        lay.addWidget(self.tab)

        # Log
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(100)
        self.log.setStyleSheet(
            "background:black; color:#0f0; font-family:monospace;")
        lay.addWidget(self.log)

    def scan(self):
        d = self.factory.robots_data
        self.tab.setRowCount(len(d))
        for i, (name, data) in enumerate(d.items()):
            if name not in self.stats:
                self.stats[name] = {"err": 0, "req": 0}

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
            if health != "OK":
                ico = "CRITICAL"

            self.tab.setItem(i, 0, QTableWidgetItem(name))
            self.tab.setItem(i, 1, QTableWidgetItem(ico))
            self.tab.setItem(i, 2, QTableWidgetItem(str(st["err"])))
            self.tab.setItem(i, 3, QTableWidgetItem(str(st["req"])))
            self.tab.setItem(i, 4, QTableWidgetItem(health))

    def report(self, name, success):
        if not name or name not in self.stats:
            return
        self.stats[name]["req"] += 1
        if not success:
            self.stats[name]["err"] += 1
        else:
            # Decrement instead of reset so threshold remains reachable
            self.stats[name]["err"] = max(0, self.stats[name]["err"] - 1)

    def force_stop(self, name, reason):
        if name in self.factory.robots_data and self.factory.robots_data[name].get("active", False):
            self.factory.robots_data[name]["active"] = False
            self.factory.save_data()
            self.factory.refresh_list()
            ts = datetime.now().strftime("%H:%M:%S")
            self.log.append(f"[{ts}] STOPPED {name}: {reason}")

    def kill_all(self):
        reply = QMessageBox.question(
            self, "EMERGENCY STOP",
            "Fermare TUTTI i robot?",
            QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            count = 0
            for n in self.factory.robots_data:
                if self.factory.robots_data[n].get("active", False):
                    self.factory.robots_data[n]["active"] = False
                    count += 1
            self.factory.save_data()
            self.factory.refresh_list()
            ts = datetime.now().strftime("%H:%M:%S")
            self.log.append(f"[{ts}] SYSTEM HALT. {count} agenti terminati.")


# ============================================================================
#  LEGACY COMPONENTS (PRESERVED)
# ============================================================================
class ConfigValidator:
    """Kept for main.py compatibility."""
    REQUIRED = {"rpa.pin": str}

    @classmethod
    def validate(cls, config, logger=None):
        return []


class RPAWorker(QThread):
    bet_placed = Signal(dict)
    bet_error = Signal(str)

    def __init__(self, executor, logger=None, monitor=None, controller=None):
        super().__init__()
        self._queue = queue.Queue()
        self._running = True
        self.executor = executor
        self.logger = logger
        self.controller = controller

    def enqueue_bet(self, signal_data):
        self._queue.put(signal_data)

    def stop(self):
        self._running = False
        self._queue.put(None)

    def run(self):
        while self._running:
            item = self._queue.get()
            if item is None:
                break
            try:
                if self.controller:
                    res = self.controller.handle_signal(item)
                    item["placed"] = res
                    item["timestamp"] = datetime.now().isoformat()
                    if res:
                        self.bet_placed.emit(item)
                    else:
                        self.bet_error.emit(f"Failed: {item.get('teams')}")
            except Exception as e:
                self.bet_error.emit(str(e))


class RPAMonitorTab(QWidget):
    def __init__(self, executor=None, rpa_worker=None, logger=None, parent=None):
        super().__init__(parent)
        self.rpa_worker = rpa_worker
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("RPA Monitor"))
        self.bet_table = QTableWidget(0, 4)
        layout.addWidget(self.bet_table)
        if self.rpa_worker:
            self.rpa_worker.bet_placed.connect(self._on_bet_placed)

    def _on_bet_placed(self, data):
        r = self.bet_table.rowCount()
        self.bet_table.insertRow(r)
        self.bet_table.setItem(r, 0, QTableWidgetItem(str(data.get("teams"))))


class SettingsTab(QWidget):
    stealth_changed = Signal(str)

    def __init__(self, config=None, logger=None, controller=None, parent=None):
        super().__init__(parent)
        self.config = config or {}
        self.controller = controller
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Settings (Stealth & Config)"))
        self.stealth_combo = QComboBox()
        self.stealth_combo.addItems(["Umano Lento", "Bilanciato", "Pro"])
        layout.addWidget(self.stealth_combo)
        self.stealth_combo.currentIndexChanged.connect(
            lambda i: self.stealth_changed.emit(["slow", "balanced", "pro"][i]))


class MoneyTab(QWidget):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        layout = QFormLayout(self)
        self.bankroll = QDoubleSpinBox()
        self.bankroll.setValue(100)
        layout.addRow("Bankroll", self.bankroll)
        btn = QPushButton("Save")
        btn.clicked.connect(self.save)
        layout.addRow(btn)

    def save(self):
        if self.controller:
            self.controller.table = RoserpinaTable(self.bankroll.value(), 3.0)


class StatsTab(QWidget):
    def __init__(self, **kwargs):
        super().__init__()
        QVBoxLayout(self).addWidget(QLabel("Statistics"))


class TrainerTab(QWidget):
    def __init__(self, controller=None, logger=None, parent=None):
        super().__init__(parent)
        self.controller = controller
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("AI Trainer"))
        self.chat_display = QTextEdit()
        layout.addWidget(self.chat_display)
        self.train_btn = QPushButton("Train Step")
        self.train_btn.clicked.connect(self._on_train_step)
        layout.addWidget(self.train_btn)

    def _on_train_step(self):
        if self.controller:
            self.controller.request_training()

    @Slot(str)
    def on_training_complete(self, res):
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
        self.setWindowTitle("SuperAgent V5.1 SENTINEL")
        self.setMinimumSize(1200, 800)

        self.rpa_worker = None
        if executor or controller:
            self.rpa_worker = RPAWorker(executor, logger, monitor, controller)
            self.rpa_worker.start()

        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        # Primary tabs
        self.factory = RobotFactoryTab(controller)
        self.supervisor = SupervisorTab(controller, self.factory)
        self.tabs.addTab(self.factory, "Factory")
        self.tabs.addTab(self.supervisor, "SUPERVISOR")

        # Legacy tabs
        self.rpa_tab = RPAMonitorTab(executor, self.rpa_worker, logger)
        self.tabs.addTab(self.rpa_tab, "RPA Monitor")

        self.settings_tab = SettingsTab(config, logger, controller)
        self.settings_tab.stealth_changed.connect(self._on_stealth_changed)
        self.tabs.addTab(self.settings_tab, "Settings")

        if self.controller:
            self.money_tab = MoneyTab(self.controller)
            self.tabs.addTab(self.money_tab, "Roserpina")

        if self.controller:
            self.mapping_tab = MappingTab(self.controller)
            self.tabs.addTab(self.mapping_tab, "Auto-Mapping")

        self.telegram_tab = TelegramTab(agent=vision)
        self.tabs.addTab(self.telegram_tab, "Telegram")

        self.stats_tab = StatsTab()
        self.tabs.addTab(self.stats_tab, "Stats")

        self.trainer_tab = TrainerTab(controller, logger)
        self.tabs.addTab(self.trainer_tab, "Trainer")

        if self.controller:
            self.controller.training_complete.connect(
                self.trainer_tab.on_training_complete)

    @Slot(str)
    def _on_stealth_changed(self, mode):
        if self.controller:
            self.controller.set_stealth_mode(mode)


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
    app = QApplication(sys.argv)
    apply_dark_theme(app)
    win = MainWindow(vision, telegram_learner, rpa_healer,
                     logger, executor, config, monitor, controller)
    win.show()
    return app.exec()
