"""
SuperAgent Desktop App V5 Sentinel - Enterprise Edition
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


# ---------------------------------------------------------------------------
#  V5 SENTINEL LAYER (AI FIREWALL)
# ---------------------------------------------------------------------------
class SafetySentinel:
    FORBIDDEN_PATTERNS = [
        "import os", "import sys", "sys.exit", "os.system", "os.remove",
        "rm -rf", "format c:", "drop table", "alter user",
        "shutdown", "reboot", "wget ", "curl "
    ]

    @staticmethod
    def scan_input(text: str) -> bool:
        text_lower = text.lower()
        for pattern in SafetySentinel.FORBIDDEN_PATTERNS:
            if pattern in text_lower:
                return False
        return True

    @staticmethod
    def sanitize_log(text: str) -> str:
        if not text:
            return ""
        return re.sub(r"(sk-[a-zA-Z0-9\-\_]{10,})", "sk-***HIDDEN***", text)

    @staticmethod
    def get_security_warning() -> str:
        return "SECURITY ALERT: Messaggio bloccato dal Sentinel Layer."


# ---------------------------------------------------------------------------
#  WORKER OPENROUTER (SENTINEL HARDENED)
# ---------------------------------------------------------------------------
class OpenRouterWorker(QThread):
    response_received = Signal(str)
    log_received = Signal(str)

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
                self.log_received.emit("Sentinel: Input bloccato.")
                self.response_received.emit(SafetySentinel.get_security_warning())
                return

        messages = [{"role": "system", "content": self.system_prompt}] + self.history
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://superagent.app",
            "X-Title": "SuperAgent V5 Sentinel"
        }
        self.log_received.emit("Connessione sicura inizializzata.")

        session = requests.Session()
        retry = Retry(total=2, backoff_factor=0.5,
                      status_forcelist=[429, 500, 502, 503, 504],
                      allowed_methods=["POST"])
        session.mount("https://", HTTPAdapter(max_retries=retry))

        success = False
        for model in self.fallback_models:
            self.log_received.emit(f"Tentativo modello: {model}")
            try:
                payload = {"model": model, "messages": messages,
                           "temperature": 0.7, "max_tokens": 1000}
                response = session.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers=headers, json=payload, timeout=15)
                if response.status_code == 200:
                    data = response.json()
                    if "choices" in data and len(data["choices"]) > 0:
                        content = data["choices"][0]["message"]["content"]
                        if not SafetySentinel.scan_input(content):
                            content = SafetySentinel.get_security_warning()
                        content = SafetySentinel.sanitize_log(content)
                        self.log_received.emit(f"Risposta valida da {model}")
                        self.response_received.emit(content)
                        success = True
                        break
                    else:
                        self.log_received.emit("API Risposta Vuota")
                elif response.status_code == 401:
                    self.log_received.emit("Errore Auth: Controlla la API Key")
                    break
                else:
                    self.log_received.emit(f"Errore HTTP {response.status_code}")
            except requests.exceptions.Timeout:
                self.log_received.emit(f"Timeout su {model}")
            except requests.exceptions.ConnectionError:
                self.log_received.emit(f"Connessione fallita su {model}")
            except Exception as e:
                self.log_received.emit(SafetySentinel.sanitize_log(str(e))[:60])
            time.sleep(0.5)

        if not success:
            self.response_received.emit("Tutti i modelli fallback falliti.")


# ---------------------------------------------------------------------------
#  TAB: ROBOT FACTORY (WITH UI LOCKING + SENTINEL)
# ---------------------------------------------------------------------------
class RobotFactoryTab(QWidget):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self.robots_file = "my_robots.json"
        self.api_file = "api_config.json"
        self.current_robot_name = None
        self.ai_busy = False
        self.robots_data = self.load_data()
        self.api_key = self.load_api_key()
        self.init_ui()

    def init_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        sidebar = QWidget()
        sidebar.setFixedWidth(280)
        sidebar.setStyleSheet("background-color: #202123; border-right: 1px solid #4d4d4f;")
        sidebar_layout = QVBoxLayout(sidebar)

        lbl_title = QLabel("FLOTTA AGENTI")
        lbl_title.setStyleSheet("color: #ececf1; font-weight: bold; font-size: 14px; padding: 10px;")
        sidebar_layout.addWidget(lbl_title)

        self.btn_new = QPushButton("+ Crea Nuovo Robot")
        self.btn_new.setStyleSheet(
            "QPushButton { border: 1px solid #565869; border-radius: 5px; color: white; "
            "padding: 10px; text-align: left; background-color: transparent; } "
            "QPushButton:hover { background-color: #2a2b32; }")
        self.btn_new.clicked.connect(self.create_robot_dialog)
        sidebar_layout.addWidget(self.btn_new)

        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet(
            "QListWidget { background: transparent; border: none; outline: none; } "
            "QListWidget::item { color: #ececf1; padding: 12px; border-radius: 5px; margin-bottom: 2px; } "
            "QListWidget::item:selected { background-color: #343541; } "
            "QListWidget::item:hover { background-color: #2a2b32; }")
        self.list_widget.currentItemChanged.connect(self.load_robot_interface)
        sidebar_layout.addWidget(self.list_widget)

        sidebar_layout.addStretch()
        api_frame = QFrame()
        api_frame.setStyleSheet("border-top: 1px solid #4d4d4f; padding-top: 10px;")
        api_layout = QVBoxLayout(api_frame)
        lbl_api = QLabel("OpenRouter API Key")
        lbl_api.setStyleSheet("color: #8e8ea0; font-size: 12px; font-weight: bold;")
        api_layout.addWidget(lbl_api)
        self.input_api_key = QLineEdit()
        self.input_api_key.setText(self.api_key)
        self.input_api_key.setPlaceholderText("sk-or-...")
        self.input_api_key.setEchoMode(QLineEdit.Password)
        self.input_api_key.setStyleSheet(
            "QLineEdit { background-color: #40414f; color: white; border: 1px solid #565869; "
            "padding: 8px; border-radius: 4px; font-size: 12px; } "
            "QLineEdit:focus { border: 1px solid #19c37d; }")
        self.input_api_key.textChanged.connect(self.save_api_key)
        api_layout.addWidget(self.input_api_key)
        sidebar_layout.addWidget(api_frame)
        main_layout.addWidget(sidebar)

        self.right_panel = QWidget()
        self.right_panel.setStyleSheet("background-color: #343541;")
        self.right_panel.setVisible(False)
        right_layout = QVBoxLayout(self.right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)

        header_frame = QFrame()
        header_frame.setStyleSheet("background-color: #343541; border-bottom: 1px solid #2d2d30; padding: 15px;")
        header_layout = QHBoxLayout(header_frame)
        self.lbl_name = QLabel("Nome Robot")
        self.lbl_name.setStyleSheet("font-size: 18px; font-weight: bold; color: white;")
        self.input_telegram = QLineEdit()
        self.input_telegram.setPlaceholderText("Canale Telegram...")
        self.input_telegram.setStyleSheet("background: #40414f; color: white; border: none; padding: 8px; border-radius: 4px;")
        self.input_telegram.setFixedWidth(220)
        self.input_telegram.textChanged.connect(self.save_current_config)
        self.btn_toggle = QPushButton("AVVIA")
        self.btn_toggle.setCheckable(True)
        self.btn_toggle.setFixedWidth(100)
        self.btn_toggle.clicked.connect(self.toggle_status)
        self.btn_delete = QPushButton("X")
        self.btn_delete.setFixedWidth(40)
        self.btn_delete.setStyleSheet("background-color: #ef4444; border-radius: 4px;")
        self.btn_delete.clicked.connect(self.delete_robot)
        header_layout.addWidget(self.lbl_name)
        header_layout.addStretch()
        header_layout.addWidget(QLabel("Target:"))
        header_layout.addWidget(self.input_telegram)
        header_layout.addWidget(self.btn_toggle)
        header_layout.addWidget(self.btn_delete)
        right_layout.addWidget(header_frame)

        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        self.chat_display.setStyleSheet("border: none; padding: 20px; color: #d1d5db; font-size: 15px; background-color: #343541;")
        right_layout.addWidget(self.chat_display)

        input_container = QWidget()
        input_container.setStyleSheet("background-color: #343541; padding: 20px;")
        input_box = QHBoxLayout(input_container)
        self.chat_input = QLineEdit()
        self.chat_input.setPlaceholderText("Istruisci il robot...")
        self.chat_input.setStyleSheet(
            "QLineEdit { background-color: #40414f; color: white; border: 1px solid #565869; "
            "padding: 12px; border-radius: 6px; font-size: 14px; } "
            "QLineEdit:focus { border: 1px solid #19c37d; }")
        self.chat_input.returnPressed.connect(self.send_message)
        self.btn_send = QPushButton("Invia")
        self.btn_send.setStyleSheet(
            "background-color: #19c37d; color: white; padding: 12px 20px; "
            "border-radius: 6px; font-weight: bold;")
        self.btn_send.clicked.connect(self.send_message)
        input_box.addWidget(self.chat_input)
        input_box.addWidget(self.btn_send)
        right_layout.addWidget(input_container)
        main_layout.addWidget(self.right_panel)
        self.refresh_list()

    def load_api_key(self):
        try:
            with open(self.api_file, "r") as f:
                return json.load(f).get("api_key", "")
        except Exception:
            return ""

    def save_api_key(self):
        key = self.input_api_key.text().strip()
        self.api_key = key
        with open(self.api_file, "w") as f:
            json.dump({"api_key": key}, f)

    def load_data(self):
        try:
            with open(self.robots_file, "r") as f:
                return json.load(f)
        except Exception:
            return {}

    def save_data(self):
        with open(self.robots_file, "w") as f:
            json.dump(self.robots_data, f, indent=4)

    def refresh_list(self):
        self.list_widget.clear()
        for name, data in self.robots_data.items():
            icon = "[ON]" if data["active"] else "[OFF]"
            self.list_widget.addItem(QListWidgetItem(f"{icon} {name}"))

    def create_robot_dialog(self):
        name, ok = QInputDialog.getText(self, "Nuovo Robot", "Nome:")
        if ok and name and name not in self.robots_data:
            self.robots_data[name] = {"active": False, "telegram": "", "chat_history": []}
            self.save_data()
            self.refresh_list()

    def load_robot_interface(self, current, previous):
        if not current:
            self.right_panel.setVisible(False)
            return
        name = current.text().replace("[ON] ", "").replace("[OFF] ", "")
        self.current_robot_name = name
        data = self.robots_data[name]
        self.right_panel.setVisible(True)
        self.lbl_name.setText(name)
        self.input_telegram.setText(data["telegram"])
        self.update_toggle_btn(data["active"])
        self.chat_display.clear()
        for msg in data["chat_history"]:
            self.append_chat_visual(msg["role"], msg["content"])

    def save_current_config(self):
        if self.current_robot_name:
            self.robots_data[self.current_robot_name]["telegram"] = self.input_telegram.text()
            self.save_data()

    def toggle_status(self):
        name = self.current_robot_name
        if not name:
            return
        self.robots_data[name]["active"] = not self.robots_data[name]["active"]
        self.save_data()
        self.update_toggle_btn(self.robots_data[name]["active"])
        self.refresh_list()

    def update_toggle_btn(self, active):
        if active:
            self.btn_toggle.setText("PAUSA")
            self.btn_toggle.setStyleSheet("background-color: #eab308; color: black; font-weight: bold; border-radius: 4px;")
        else:
            self.btn_toggle.setText("AVVIA")
            self.btn_toggle.setStyleSheet("background-color: #22c55e; color: white; font-weight: bold; border-radius: 4px;")

    def delete_robot(self):
        name = self.current_robot_name
        confirm = QMessageBox.question(self, "Elimina", f"Cancellare {name}?", QMessageBox.Yes | QMessageBox.No)
        if confirm == QMessageBox.Yes:
            del self.robots_data[name]
            self.save_data()
            self.right_panel.setVisible(False)
            self.refresh_list()

    def set_ui_busy(self, busy):
        self.ai_busy = busy
        self.chat_input.setEnabled(not busy)
        self.btn_send.setEnabled(not busy)
        if busy:
            self.chat_input.setPlaceholderText("Attendi risposta...")
            self.btn_send.setText("...")
        else:
            self.chat_input.setPlaceholderText("Istruisci il robot...")
            self.btn_send.setText("Invia")
            self.chat_input.setFocus()

    def send_message(self):
        if self.ai_busy:
            return
        text = self.chat_input.text().strip()
        if not text:
            return
        if not SafetySentinel.scan_input(text):
            self.append_chat_visual("system", "COMANDO BLOCCATO DAL SENTINEL")
            self.chat_input.clear()
            return
        if not self.api_key or len(self.api_key) < 10:
            QMessageBox.critical(self, "API Key Mancante", "Inserisci la chiave OpenRouter nella sidebar!")
            return

        name = self.current_robot_name
        self.set_ui_busy(True)
        self.append_chat_visual("user", text)
        self.robots_data[name]["chat_history"].append({"role": "user", "content": text})
        self.save_data()
        self.chat_input.clear()

        history = self.robots_data[name]["chat_history"]
        sys_prompt = f"Sei {name}, robot di betting. Telegram: {self.robots_data[name]['telegram']}."
        self.chat_display.append("<i style='color: gray; font-size: 12px;'>Sentinel sta analizzando...</i>")
        self.worker = OpenRouterWorker(self.api_key, history, sys_prompt)
        self.worker.response_received.connect(self.on_ai_response)
        self.worker.log_received.connect(self.on_ai_log)
        self.worker.finished.connect(lambda: self.set_ui_busy(False))
        self.worker.start()

    def on_ai_log(self, text):
        self.chat_display.append(f"<div style='color: #888; font-family: monospace; font-size: 11px;'>{text}</div>")
        self.chat_display.moveCursor(QTextCursor.End)

    def on_ai_response(self, text):
        self.append_chat_visual("assistant", text)
        self.robots_data[self.current_robot_name]["chat_history"].append({"role": "assistant", "content": text})
        self.save_data()
        main_win = self.window()
        if hasattr(main_win, "supervisor"):
            main_win.supervisor.report_activity(self.current_robot_name, success=True)

    def append_chat_visual(self, role, text):
        if role == "system":
            color, sender = "#ff4444", "SENTINEL"
        elif role == "user":
            color, sender = "#a8b1ff", "TU"
        else:
            color, sender = "#19c37d", "ROBOT"
        html = (f"<div style='margin-bottom: 10px;'>"
                f"<b style='color: {color};'>{sender}</b><br>"
                f"<span style='color: #ececf1;'>{text}</span></div>")
        self.chat_display.append(html)
        self.chat_display.moveCursor(QTextCursor.End)


# ---------------------------------------------------------------------------
#  V5.1 SUPERVISOR CORE (WATCHDOG & KILL SWITCH)
# ---------------------------------------------------------------------------
class SupervisorTab(QWidget):
    def __init__(self, controller, robot_factory):
        super().__init__()
        self.controller = controller
        self.factory = robot_factory
        self.stats = {}
        self.watchdog_timer = QTimer()
        self.watchdog_timer.timeout.connect(self.scan_vital_signs)
        self.watchdog_timer.start(2000)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        header = QFrame()
        header.setStyleSheet("background: #2d2d30; border-radius: 8px; padding: 10px;")
        h_layout = QHBoxLayout(header)
        lbl = QLabel("SUPERVISOR ACTIVE")
        lbl.setStyleSheet("color: #00ff00; font-weight: bold; font-size: 16px; letter-spacing: 1px;")
        self.btn_kill_all = QPushButton("EMERGENCY STOP")
        self.btn_kill_all.setFixedSize(180, 40)
        self.btn_kill_all.setStyleSheet(
            "QPushButton { background-color: #ff0000; color: white; font-weight: bold; "
            "border: 2px solid #550000; border-radius: 5px; } "
            "QPushButton:hover { background-color: #ff4444; } "
            "QPushButton:pressed { background-color: #aa0000; }")
        self.btn_kill_all.clicked.connect(self.emergency_stop)
        h_layout.addWidget(lbl)
        h_layout.addStretch()
        h_layout.addWidget(self.btn_kill_all)
        layout.addWidget(header)

        self.monitor_table = QTableWidget()
        self.monitor_table.setColumnCount(5)
        self.monitor_table.setHorizontalHeaderLabels(["AGENTE", "STATO", "ERRORI (1h)", "TOKEN USAGE", "HEALTH"])
        self.monitor_table.horizontalHeader().setStretchLastSection(True)
        self.monitor_table.setStyleSheet("background: #1e1e1e; color: white; border: none; font-family: Consolas;")
        layout.addWidget(self.monitor_table)

        self.log_console = QTextEdit()
        self.log_console.setReadOnly(True)
        self.log_console.setMaximumHeight(150)
        self.log_console.setStyleSheet("background: #000; color: #0f0; font-family: monospace; font-size: 11px;")
        layout.addWidget(self.log_console)

    def scan_vital_signs(self):
        robots = self.factory.robots_data
        self.monitor_table.setRowCount(len(robots))
        row = 0
        for name, data in robots.items():
            if name not in self.stats:
                self.stats[name] = {"errors": 0, "calls": 0, "status": "IDLE"}
            is_active = data.get("active", False)
            errors = self.stats[name]["errors"]
            calls = self.stats[name]["calls"]
            health_status = "HEALTHY"
            if errors > 5:
                self.force_stop_agent(name, "TOO MANY ERRORS")
                health_status = "KILLED (Errors)"
            elif calls > 50:
                self.force_stop_agent(name, "API FLOODING")
                health_status = "PAUSED (Spam)"
            status_icon = "RUNNING" if is_active else "SLEEPING"
            if health_status != "HEALTHY":
                status_icon = "CRITICAL"
            self.monitor_table.setItem(row, 0, QTableWidgetItem(name))
            self.monitor_table.setItem(row, 1, QTableWidgetItem(status_icon))
            self.monitor_table.setItem(row, 2, QTableWidgetItem(str(errors)))
            self.monitor_table.setItem(row, 3, QTableWidgetItem(f"{calls} req"))
            self.monitor_table.setItem(row, 4, QTableWidgetItem(health_status))
            row += 1

    def report_activity(self, robot_name, success):
        if robot_name not in self.stats:
            return
        self.stats[robot_name]["calls"] += 1
        if not success:
            self.stats[robot_name]["errors"] += 1
        else:
            self.stats[robot_name]["errors"] = 0

    def force_stop_agent(self, name, reason):
        if name in self.factory.robots_data and self.factory.robots_data[name]["active"]:
            self.factory.robots_data[name]["active"] = False
            self.factory.save_data()
            self.factory.refresh_list()
            ts = datetime.now().strftime("%H:%M:%S")
            self.log_console.append(f"[{ts}] SUPERVISOR: Agente '{name}' arrestato! Motivo: {reason}")

    def emergency_stop(self):
        reply = QMessageBox.question(
            self, "EMERGENCY STOP",
            "Sei sicuro? Questo arrestera TUTTI i robot immediatamente.",
            QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            count = 0
            for name in self.factory.robots_data:
                if self.factory.robots_data[name]["active"]:
                    self.factory.robots_data[name]["active"] = False
                    count += 1
            self.factory.save_data()
            self.factory.refresh_list()
            ts = datetime.now().strftime("%H:%M:%S")
            self.log_console.append(f"[{ts}] EMERGENCY STOP ATTIVATO. {count} agenti terminati.")
            QMessageBox.warning(self, "SYSTEM HALT", f"Tutti i {count} agenti sono stati spenti forzatamente.")


# ---------------------------------------------------------------------------
#  CLASSIC COMPONENTS (PRESERVED)
# ---------------------------------------------------------------------------
class ConfigValidator:
    REQUIRED = {"rpa.pin": str}
    @classmethod
    def validate(cls, config, logger=None):
        return []


class AIWorker(QThread):
    response_ready = Signal(str)
    error_occurred = Signal(str)
    def __init__(self, vision_learner, prompt):
        super().__init__()
        self.vision = vision_learner
        self.prompt = prompt
    def run(self):
        try:
            res = self.vision.understand_text(self.prompt) if self.vision else "No AI"
            self.response_ready.emit(str(res))
        except Exception as e:
            self.error_occurred.emit(str(e))


class TrainerWorker(QThread):
    response_ready = Signal(str)
    error_occurred = Signal(str)
    def __init__(self, controller, question, include_dom=False, include_screenshot=False):
        super().__init__()
        self.controller = controller
        self.question = question
        self.include_dom = include_dom
        self.include_screenshot = include_screenshot
    def run(self):
        try:
            res = self.controller.ask_trainer(self.question, self.include_dom, self.include_screenshot)
            self.response_ready.emit(res or "No response.")
        except Exception as e:
            self.error_occurred.emit(str(e))


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


class ChatTab(QWidget):
    def __init__(self, vision_learner=None, logger=None, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Legacy Chat"))
        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        layout.addWidget(self.chat_display)


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


# ---------------------------------------------------------------------------
#  MAIN WINDOW
# ---------------------------------------------------------------------------
class MainWindow(QMainWindow):
    def __init__(self, vision=None, telegram_learner=None, rpa_healer=None,
                 logger=None, executor=None, config=None, monitor=None,
                 controller=None):
        super().__init__()
        self.controller = controller
        self.setWindowTitle("SuperAgent H24 V5 Sentinel")
        self.setMinimumSize(1200, 800)

        self.rpa_worker = None
        if executor or controller:
            self.rpa_worker = RPAWorker(executor, logger, monitor, controller)
            self.rpa_worker.start()

        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        self.robot_factory = RobotFactoryTab(self.controller)
        self.supervisor = SupervisorTab(self.controller, self.robot_factory)

        self.tabs.addTab(self.robot_factory, "Robot Factory")
        self.tabs.addTab(self.supervisor, "SUPERVISOR CORE")

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
        self.tabs.addTab(self.trainer_tab, "Trainer Legacy")

        if self.controller:
            self.controller.training_complete.connect(self.trainer_tab.on_training_complete)

    @Slot(str)
    def _on_stealth_changed(self, mode):
        print(f"Stealth changed: {mode}")


def apply_dark_theme(app):
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(53, 53, 53))
    palette.setColor(QPalette.WindowText, Qt.white)
    palette.setColor(QPalette.Base, QColor(25, 25, 25))
    palette.setColor(QPalette.AlternateBase, QColor(53, 53, 53))
    palette.setColor(QPalette.ToolTipBase, Qt.white)
    palette.setColor(QPalette.ToolTipText, Qt.white)
    palette.setColor(QPalette.Text, Qt.white)
    palette.setColor(QPalette.Button, QColor(53, 53, 53))
    palette.setColor(QPalette.ButtonText, Qt.white)
    palette.setColor(QPalette.BrightText, Qt.red)
    palette.setColor(QPalette.Link, QColor(42, 130, 218))
    palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
    palette.setColor(QPalette.HighlightedText, Qt.black)
    app.setPalette(palette)


def run_app(vision=None, telegram_learner=None, rpa_healer=None,
            logger=None, executor=None, config=None, monitor=None,
            controller=None):
    app = QApplication(sys.argv)
    apply_dark_theme(app)
    win = MainWindow(vision, telegram_learner, rpa_healer,
                     logger, executor, config, monitor, controller)
    win.show()
    return app.exec()
