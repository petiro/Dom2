"""
SuperAgent Desktop UI - Modern Interface (Singleton & Immortality Edition)
Sincronizzato con l'architettura Singleton Executor e HealthMonitor.
"""
import sys
import os
import json
import yaml
import time
from datetime import datetime
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QTextEdit, QPushButton, QLabel, QLineEdit,
    QTableWidget, QTableWidgetItem, QSplitter, QStatusBar,
    QGroupBox, QCheckBox, QSpinBox, QProgressBar, QMessageBox,
    QComboBox
)
from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtGui import QFont, QColor, QPalette
from ui.telegram_tab import TelegramTab

# PATCH: Importiamo il battito cardiaco globale dal main
import main

# Resolve BASE_DIR for config paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class AIWorker(QThread):
    """Worker thread for AI processing to avoid UI blocking"""
    finished = Signal(str)
    error = Signal(str)

    def __init__(self, vision_learner, prompt):
        super().__init__()
        self.vision = vision_learner
        self.prompt = prompt

    def run(self):
        try:
            result = self.vision.understand_text(self.prompt)
            if result:
                self.finished.emit(json.dumps(result, indent=2, ensure_ascii=False))
            else:
                self.error.emit("No response from AI")
        except Exception as e:
            self.error.emit(f"Error: {str(e)}")


class ChatTab(QWidget):
    """AI Chat interface tab"""

    def __init__(self, vision_learner, parent=None):
        super().__init__(parent)
        self.vision = vision_learner
        self.worker = None
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        title = QLabel("AI Assistant")
        title.setFont(QFont("Arial", 16, QFont.Bold))
        layout.addWidget(title)

        self.chat_history = QTextEdit()
        self.chat_history.setReadOnly(True)
        self.chat_history.setPlaceholderText("AI responses will appear here...")
        layout.addWidget(self.chat_history)

        input_group = QGroupBox("Your Message")
        input_layout = QVBoxLayout(input_group)

        self.input_text = QTextEdit()
        self.input_text.setPlaceholderText("Type your message here...")
        self.input_text.setMaximumHeight(100)
        input_layout.addWidget(self.input_text)

        btn_layout = QHBoxLayout()

        self.send_btn = QPushButton("Send")
        self.send_btn.clicked.connect(self.send_message)
        self.send_btn.setStyleSheet("background-color: #4CAF50; color: white; padding: 10px; font-weight: bold;")

        self.clear_btn = QPushButton("Clear")
        self.clear_btn.clicked.connect(self.clear_chat)

        btn_layout.addWidget(self.send_btn)
        btn_layout.addWidget(self.clear_btn)
        btn_layout.addStretch()

        input_layout.addLayout(btn_layout)
        layout.addWidget(input_group)

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        self.progress.setRange(0, 0)
        layout.addWidget(self.progress)

    def send_message(self):
        if not self.vision:
            QMessageBox.warning(self, "Error", "AI not initialized. Check API key in settings.")
            return

        prompt = self.input_text.toPlainText().strip()
        if not prompt:
            return

        self.append_message("You", prompt, "#2196F3")
        self.send_btn.setEnabled(False)
        self.progress.setVisible(True)

        self.worker = AIWorker(self.vision, prompt)
        self.worker.finished.connect(self.on_response)
        self.worker.error.connect(self.on_error)
        self.worker.start()
        self.input_text.clear()

    def on_response(self, response):
        self.append_message("AI", response, "#4CAF50")
        self.send_btn.setEnabled(True)
        self.progress.setVisible(False)

    def on_error(self, error):
        self.append_message("Error", error, "#f44336")
        self.send_btn.setEnabled(True)
        self.progress.setVisible(False)

    def append_message(self, sender, message, color):
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted = f'<div style="margin: 10px 0; padding: 10px; background-color: {color}20; border-left: 3px solid {color};">'
        formatted += f'<b style="color: {color};">[{timestamp}] {sender}:</b><br>'
        formatted += f'<span style="color: #333;">{message}</span>'
        formatted += '</div>'
        self.chat_history.append(formatted)

    def clear_chat(self):
        self.chat_history.clear()


class RPAWorker(QThread):
    """
    Worker per l'automazione browser.
    Usa l'executor SINGLETON passato dal main, evitando conflitti di profilo.
    """
    status_changed = Signal(str, str)  # status, color
    error_occurred = Signal(str)
    task_completed = Signal()
    healing_performed = Signal(str, str, str, str)  # timestamp, key, old, new
    log_signal = Signal(str)

    def __init__(self, logger, rpa_healer=None, headless=False, use_real_chrome=True, chrome_profile="Default", executor=None):
        super().__init__()
        self.logger = logger
        self.rpa_healer = rpa_healer
        self.headless = headless
        self.use_real_chrome = use_real_chrome
        self.chrome_profile = chrome_profile
        self.running = False
        self.executor = executor  # Use shared singleton executor if provided
        self._owns_executor = executor is None  # Track if we created it (for cleanup)

    def run(self):
        self.running = True
        try:
            # Only create a new executor if none was provided (singleton pattern)
            if self.executor is None:
                from core.dom_executor_playwright import DomExecutorPlaywright
                self.executor = DomExecutorPlaywright(
                    logger=self.logger,
                    headless=self.headless,
                    allow_place=False,
                    use_real_chrome=self.use_real_chrome,
                    chrome_profile=self.chrome_profile
                )
                self._owns_executor = True

            # Initialize browser immediately (lazy init won't trigger otherwise)
            if not self.executor._ensure_browser():
                self.error_occurred.emit("Failed to start browser. Run: playwright install chromium")
                return

            self.status_changed.emit("RUNNING", "green")
            self.log_signal.emit("RPA Worker avviato utilizzando Singleton Executor...")

            # Aggiorna heartbeat
            main.last_heartbeat = time.time()

            # Load selectors config
            selectors_path = os.path.join(BASE_DIR, "config", "selectors.yaml")
            selectors = {}
            if os.path.exists(selectors_path):
                with open(selectors_path, "r", encoding="utf-8") as f:
                    selectors = yaml.safe_load(f) or {}

            # Navigate to target site
            try:
                self.logger.info("Navigating to bet365...")
                self.executor.page.goto("https://www.bet365.it/#/HO/", timeout=30000)
                self.executor._wait_for_page_ready()
                self.logger.info("Page loaded, starting selector monitoring")
            except Exception as e:
                self.logger.warning(f"Navigation failed (will retry): {e}")

            heal_interval = 30
            last_heal_check = 0

            while self.running:
                time.sleep(1)

                # Aggiorna heartbeat durante operazioni lunghe
                main.last_heartbeat = time.time()

                # Periodic self-healing check
                if (self.rpa_healer and self.executor._initialized
                        and selectors and time.time() - last_heal_check > heal_interval):
                    last_heal_check = time.time()
                    try:
                        if not self.executor._recover_page():
                            self.logger.error("Page recovery failed, skipping healing cycle")
                            continue

                        results = self.rpa_healer.test_all_selectors(
                            self.executor.page, selectors
                        )
                        broken = [k for k, v in results.items() if not v]

                        if broken:
                            total = len(selectors)
                            broken_ratio = len(broken) / total if total > 0 else 0

                            if broken_ratio > 0.5:
                                self.logger.info(
                                    f"MAJOR CHANGE: {len(broken)}/{total} selectors broken "
                                    f"({broken_ratio:.0%}). Triggering full site relearn..."
                                )
                                relearned = self.rpa_healer.full_site_relearn(
                                    self.executor.page
                                )
                                for key, new_sel in relearned.items():
                                    old_sel = selectors.get(key, "N/A")
                                    selectors[key] = new_sel
                                    ts = datetime.now().strftime("%H:%M:%S")
                                    self.healing_performed.emit(ts, key, str(old_sel), new_sel)
                                    self.task_completed.emit()
                            else:
                                self.logger.info(f"Broken selectors: {broken}")
                                descriptions = {k: k.replace("_", " ") for k in broken}
                                healed = self.rpa_healer.auto_heal_all(
                                    self.executor.page, descriptions
                                )
                                for key, new_sel in healed.items():
                                    old_sel = selectors.get(key, "N/A")
                                    selectors[key] = new_sel
                                    ts = datetime.now().strftime("%H:%M:%S")
                                    self.healing_performed.emit(ts, key, str(old_sel), new_sel)
                                    self.task_completed.emit()
                    except Exception as e:
                        self.logger.error(f"Healing check error: {e}")

        except Exception as e:
            self.error_occurred.emit(f"RPA Error: {str(e)}")
        finally:
            # Only close executor if we created it (not the shared singleton)
            if self.executor and self._owns_executor:
                self.executor.close()
            self.status_changed.emit("STOPPED", "gray")

    def stop(self):
        self.running = False


class RPAMonitorTab(QWidget):
    """RPA monitoring and control tab"""

    def __init__(self, logger=None, rpa_healer=None, parent=None, executor=None):
        super().__init__(parent)
        self.logger = logger
        self.rpa_healer = rpa_healer
        self.executor = executor  # Shared singleton executor
        self.rpa_worker = None
        self.tasks_completed = 0
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        title = QLabel("RPA Monitor")
        title.setFont(QFont("Arial", 16, QFont.Bold))
        layout.addWidget(title)

        status_group = QGroupBox("Agent Status")
        status_layout = QVBoxLayout(status_group)

        self.status_label = QLabel("Status: <b style='color: gray;'>IDLE</b>")
        self.uptime_label = QLabel("Uptime: 0 seconds")
        self.tasks_label = QLabel("Tasks completed: 0")

        status_layout.addWidget(self.status_label)
        status_layout.addWidget(self.uptime_label)
        status_layout.addWidget(self.tasks_label)

        layout.addWidget(status_group)

        healing_group = QGroupBox("Selector Healing")
        healing_layout = QVBoxLayout(healing_group)

        self.healing_table = QTableWidget()
        self.healing_table.setColumnCount(4)
        self.healing_table.setHorizontalHeaderLabels(["Timestamp", "Selector", "Old", "New"])
        self.healing_table.horizontalHeader().setStretchLastSection(True)

        healing_layout.addWidget(self.healing_table)

        layout.addWidget(healing_group)

        control_layout = QHBoxLayout()

        self.start_btn = QPushButton("Start Agent")
        self.start_btn.setStyleSheet("background-color: #4CAF50; color: white; padding: 10px;")
        self.start_btn.clicked.connect(self.start_agent)

        self.stop_btn = QPushButton("Stop Agent")
        self.stop_btn.setEnabled(False)
        self.stop_btn.setStyleSheet("background-color: #f44336; color: white; padding: 10px;")
        self.stop_btn.clicked.connect(self.stop_agent)

        self.test_healing_btn = QPushButton("Test Healing")
        self.test_healing_btn.clicked.connect(self.test_healing)

        control_layout.addWidget(self.start_btn)
        control_layout.addWidget(self.stop_btn)
        control_layout.addWidget(self.test_healing_btn)
        control_layout.addStretch()

        layout.addLayout(control_layout)

    def start_agent(self):
        """Start the RPA agent"""
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)

        # Read chrome settings from config
        config_path = os.path.join(BASE_DIR, "config", "config.yaml")
        use_real_chrome = True
        chrome_profile = "Default"
        headless = False
        try:
            import yaml as _yaml
            with open(config_path, "r", encoding="utf-8") as _f:
                _cfg = _yaml.safe_load(_f) or {}
            rpa_cfg = _cfg.get("rpa", {})
            use_real_chrome = rpa_cfg.get("use_real_chrome", True)
            chrome_profile = rpa_cfg.get("chrome_profile", "Default")
            headless = rpa_cfg.get("headless", False)
        except Exception:
            pass

        self.rpa_worker = RPAWorker(
            logger=self.logger,
            rpa_healer=self.rpa_healer,
            headless=headless,
            use_real_chrome=use_real_chrome,
            chrome_profile=chrome_profile,
            executor=self.executor,
        )
        self.rpa_worker.status_changed.connect(self.on_status_changed)
        self.rpa_worker.error_occurred.connect(self.on_error)
        self.rpa_worker.task_completed.connect(self.on_task_completed)
        self.rpa_worker.healing_performed.connect(self.add_healing_record)
        self.rpa_worker.start()

    def stop_agent(self):
        """Stop the RPA agent"""
        if self.rpa_worker:
            self.rpa_worker.stop()
            self.rpa_worker.wait(5000)
            self.rpa_worker = None

        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.update_status("IDLE", "gray")

    def on_status_changed(self, status, color):
        self.update_status(status, color)

    def on_error(self, error):
        QMessageBox.warning(self, "RPA Error", error)
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)

    def on_task_completed(self):
        self.tasks_completed += 1
        self.tasks_label.setText(f"Tasks completed: {self.tasks_completed}")

    def test_healing(self):
        QMessageBox.information(
            self, "Selector Healing",
            "Selector healing runs automatically when the RPA agent detects "
            "that a website element has moved or changed.\n\n"
            "The AI takes a screenshot and finds the new CSS selector."
        )

    def update_status(self, status, color):
        self.status_label.setText(f"Status: <b style='color: {color};'>{status}</b>")

    def add_healing_record(self, timestamp, selector, old, new):
        row = self.healing_table.rowCount()
        self.healing_table.insertRow(row)
        self.healing_table.setItem(row, 0, QTableWidgetItem(timestamp))
        self.healing_table.setItem(row, 1, QTableWidgetItem(selector))
        self.healing_table.setItem(row, 2, QTableWidgetItem(old))
        self.healing_table.setItem(row, 3, QTableWidgetItem(new))


class StatsTab(QWidget):
    """Statistics and learning progress tab"""

    def __init__(self, telegram_learner=None, parent=None):
        super().__init__(parent)
        self.telegram_learner = telegram_learner
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        title = QLabel("Learning Statistics")
        title.setFont(QFont("Arial", 16, QFont.Bold))
        layout.addWidget(title)

        telegram_group = QGroupBox("Telegram Learning")
        telegram_layout = QVBoxLayout(telegram_group)

        self.telegram_messages = QLabel("Total messages: 0")
        self.telegram_patterns = QLabel("Learned patterns: 0")
        self.telegram_success = QLabel("Success rate: 0%")

        telegram_layout.addWidget(self.telegram_messages)
        telegram_layout.addWidget(self.telegram_patterns)
        telegram_layout.addWidget(self.telegram_success)

        layout.addWidget(telegram_group)

        rpa_group = QGroupBox("RPA Self-Healing")
        rpa_layout = QVBoxLayout(rpa_group)

        self.rpa_healings = QLabel("Total healings: 0")
        self.rpa_auto_updated = QLabel("Auto-updated: 0")
        self.rpa_success = QLabel("Success rate: 0%")

        rpa_layout.addWidget(self.rpa_healings)
        rpa_layout.addWidget(self.rpa_auto_updated)
        rpa_layout.addWidget(self.rpa_success)

        layout.addWidget(rpa_group)

        refresh_btn = QPushButton("Refresh Stats")
        refresh_btn.clicked.connect(self.refresh_stats)
        layout.addWidget(refresh_btn)

        layout.addStretch()

    def refresh_stats(self):
        if self.telegram_learner:
            stats = self.telegram_learner.get_statistics()
            self.update_telegram_stats(
                stats.get("total_messages", 0),
                stats.get("active_patterns", 0),
                stats.get("success_rate", 0.0)
            )

        history_file = os.path.join(BASE_DIR, "data", "healing_history.json")
        if os.path.exists(history_file):
            try:
                with open(history_file, "r", encoding="utf-8") as f:
                    history = json.load(f)
                total = len(history)
                auto = sum(1 for h in history if h.get("auto_updated"))
                self.update_rpa_stats(total, auto, 1.0 if total > 0 else 0.0)
            except Exception:
                pass

    def update_telegram_stats(self, total, patterns, success_rate):
        self.telegram_messages.setText(f"Total messages: {total}")
        self.telegram_patterns.setText(f"Learned patterns: {patterns}")
        self.telegram_success.setText(f"Success rate: {success_rate:.1%}")

    def update_rpa_stats(self, healings, auto_updated, success_rate):
        self.rpa_healings.setText(f"Total healings: {healings}")
        self.rpa_auto_updated.setText(f"Auto-updated: {auto_updated}")
        self.rpa_success.setText(f"Success rate: {success_rate:.1%}")


class SettingsTab(QWidget):
    """Settings and configuration tab"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.config_path = os.path.join(BASE_DIR, "config", "config.yaml")
        self.init_ui()
        self._load_current_settings()

    def init_ui(self):
        layout = QVBoxLayout(self)

        title = QLabel("Settings")
        title.setFont(QFont("Arial", 16, QFont.Bold))
        layout.addWidget(title)

        api_group = QGroupBox("API Configuration")
        api_layout = QVBoxLayout(api_group)

        api_layout.addWidget(QLabel("OpenRouter API Key:"))
        self.api_key_input = QLineEdit()
        self.api_key_input.setEchoMode(QLineEdit.Password)
        self.api_key_input.setPlaceholderText("sk-or-v1-...")
        api_layout.addWidget(self.api_key_input)

        api_layout.addWidget(QLabel("Model:"))
        self.model_select = QComboBox()
        self.model_select.addItems([
            "google/gemini-2.0-flash-exp:free",
            "meta-llama/llama-3.2-3b-instruct:free",
            "google/gemini-flash-1.5:free"
        ])
        api_layout.addWidget(self.model_select)

        layout.addWidget(api_group)

        rpa_group = QGroupBox("RPA Settings")
        rpa_layout = QVBoxLayout(rpa_group)

        self.autobet_check = QCheckBox("Enable Auto-Bet (USE WITH CAUTION)")
        self.headless_check = QCheckBox("Headless browser")
        self.headless_check.setChecked(True)

        rpa_layout.addWidget(self.autobet_check)
        rpa_layout.addWidget(self.headless_check)

        layout.addWidget(rpa_group)

        learning_group = QGroupBox("Learning Settings")
        learning_layout = QVBoxLayout(learning_group)

        self.telegram_learning_check = QCheckBox("Enable Telegram Learning")
        self.telegram_learning_check.setChecked(True)

        self.rpa_healing_check = QCheckBox("Enable RPA Self-Healing")
        self.rpa_healing_check.setChecked(True)

        learning_layout.addWidget(self.telegram_learning_check)
        learning_layout.addWidget(self.rpa_healing_check)

        layout.addWidget(learning_group)

        save_btn = QPushButton("Save Settings")
        save_btn.setStyleSheet("background-color: #2196F3; color: white; padding: 10px; font-weight: bold;")
        save_btn.clicked.connect(self.save_settings)
        layout.addWidget(save_btn)

        layout.addStretch()

    def _load_current_settings(self):
        if not os.path.exists(self.config_path):
            return
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f) or {}

            api_key = config.get("openrouter", {}).get("api_key", "")
            if api_key and api_key != "INSERISCI_KEY":
                self.api_key_input.setText(api_key)

            model = config.get("openrouter", {}).get("model", "")
            idx = self.model_select.findText(model)
            if idx >= 0:
                self.model_select.setCurrentIndex(idx)

            rpa = config.get("rpa", {})
            self.autobet_check.setChecked(rpa.get("autobet", False))
            self.headless_check.setChecked(rpa.get("headless", True))

            learning = config.get("learning", {})
            self.telegram_learning_check.setChecked(
                learning.get("telegram", {}).get("enabled", True)
            )
            self.rpa_healing_check.setChecked(
                learning.get("rpa_healing", {}).get("enabled", True)
            )
        except Exception:
            pass

    def save_settings(self):
        try:
            config = {}
            if os.path.exists(self.config_path):
                with open(self.config_path, "r", encoding="utf-8") as f:
                    config = yaml.safe_load(f) or {}

            if "openrouter" not in config:
                config["openrouter"] = {}
            api_key = self.api_key_input.text().strip()
            if api_key:
                config["openrouter"]["api_key"] = api_key
            config["openrouter"]["model"] = self.model_select.currentText()

            if "rpa" not in config:
                config["rpa"] = {}
            config["rpa"]["autobet"] = self.autobet_check.isChecked()
            config["rpa"]["headless"] = self.headless_check.isChecked()

            if "learning" not in config:
                config["learning"] = {}
            if "telegram" not in config["learning"]:
                config["learning"]["telegram"] = {}
            config["learning"]["telegram"]["enabled"] = self.telegram_learning_check.isChecked()
            if "rpa_healing" not in config["learning"]:
                config["learning"]["rpa_healing"] = {}
            config["learning"]["rpa_healing"]["enabled"] = self.rpa_healing_check.isChecked()

            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            with open(self.config_path, "w", encoding="utf-8") as f:
                yaml.dump(config, f, default_flow_style=False, allow_unicode=True)

            QMessageBox.information(self, "Settings", "Settings saved to config.yaml!")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save settings: {e}")

    def get_settings(self):
        return {
            "api_key": self.api_key_input.text(),
            "model": self.model_select.currentText(),
            "autobet": self.autobet_check.isChecked(),
            "headless": self.headless_check.isChecked(),
            "telegram_learning": self.telegram_learning_check.isChecked(),
            "rpa_healing": self.rpa_healing_check.isChecked()
        }


class ConfigValidator:
    """Validate configuration at startup and report issues."""

    @staticmethod
    def validate():
        """Returns list of (severity, message) tuples. severity: 'error' or 'warning'."""
        issues = []
        config_path = os.path.join(BASE_DIR, "config", "config.yaml")

        if not os.path.exists(config_path):
            issues.append(("error", "config/config.yaml non trovato!"))
            return issues

        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f) or {}
        except Exception as e:
            issues.append(("error", f"Errore lettura config.yaml: {e}"))
            return issues

        api_key = config.get("openrouter", {}).get("api_key", "")
        if not api_key or api_key == "INSERISCI_KEY":
            issues.append(("warning", "API Key OpenRouter mancante — le funzioni AI saranno disabilitate. Configura in Settings."))

        tg = config.get("telegram", {})
        tg_id = tg.get("api_id", "")
        tg_hash = tg.get("api_hash", "")
        if not tg_id or not tg_hash:
            issues.append(("warning", "Credenziali Telegram mancanti (api_id/api_hash) — configura dal tab Telegram."))

        return issues


class MainWindow(QMainWindow):
    """Main application window (H24 Immortal Edition)"""

    def __init__(self, vision_learner=None, telegram_learner=None,
                 rpa_healer=None, logger=None, executor=None):
        super().__init__()
        self.setWindowTitle("SuperAgent Pro - H24 Immortal Edition")
        self.resize(1200, 800)
        self.start_time = datetime.now()

        # Iniezione Dipendenze (Singleton)
        self.vision = vision_learner
        self.telegram_learner = telegram_learner
        self.rpa_healer = rpa_healer
        self.logger = logger
        self.executor = executor  # Il browser unico (Singleton)

        self.setup_ui()

        # Timer per l'Heartbeat della UI (ogni 30 secondi)
        self.heartbeat_timer = QTimer()
        self.heartbeat_timer.timeout.connect(self.send_heartbeat)
        self.heartbeat_timer.start(30000)

        # Run config validation and show overlay if issues found
        self._show_config_warnings()

    def send_heartbeat(self):
        """Aggiorna il timestamp nel main per evitare il freeze-restart."""
        main.last_heartbeat = time.time()
        self.update_status()

    def setup_ui(self):
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        # Inizializza tutti i Tab passandogli le dipendenze
        self.chat_tab = ChatTab(self.vision)
        self.rpa_tab = RPAMonitorTab(logger=self.logger, rpa_healer=self.rpa_healer, executor=self.executor)
        self.telegram_tab = TelegramTab(None, self.telegram_learner, self.logger, executor=self.executor)
        self.stats_tab = StatsTab(telegram_learner=self.telegram_learner)
        self.settings_tab = SettingsTab()

        self.tabs.addTab(self.chat_tab, "AI Chat")
        self.tabs.addTab(self.rpa_tab, "RPA Monitor")
        self.tabs.addTab(self.telegram_tab, "Telegram")
        self.tabs.addTab(self.stats_tab, "Statistics")
        self.tabs.addTab(self.settings_tab, "Settings")

        # Status Bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.apply_theme()

    def apply_theme(self):
        """Tema Dark Professionale."""
        palette = QPalette()
        palette.setColor(QPalette.Window, QColor(45, 45, 45))
        palette.setColor(QPalette.WindowText, Qt.white)
        palette.setColor(QPalette.Base, QColor(30, 30, 30))
        palette.setColor(QPalette.AlternateBase, QColor(45, 45, 45))
        palette.setColor(QPalette.ToolTipBase, Qt.white)
        palette.setColor(QPalette.ToolTipText, Qt.white)
        palette.setColor(QPalette.Text, Qt.white)
        palette.setColor(QPalette.Button, QColor(45, 45, 45))
        palette.setColor(QPalette.ButtonText, Qt.white)
        palette.setColor(QPalette.Link, QColor(42, 130, 218))
        palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
        palette.setColor(QPalette.HighlightedText, Qt.black)
        self.setPalette(palette)

    def update_status(self):
        uptime = datetime.now() - self.start_time
        self.status_bar.showMessage(
            f"Uptime: {int(uptime.total_seconds())}s | Browser: {'Attivo' if self.executor else 'Offline'}"
        )

    def _show_config_warnings(self):
        """Validate config at startup and show overlay banner for issues."""
        issues = ConfigValidator.validate()
        if not issues:
            return

        errors = [msg for sev, msg in issues if sev == "error"]
        warnings = [msg for sev, msg in issues if sev == "warning"]

        if errors:
            text = "<b>ERRORI CONFIGURAZIONE:</b><br>" + "<br>".join(f"- {e}" for e in errors)
            if warnings:
                text += "<br><br><b>Avvisi:</b><br>" + "<br>".join(f"- {w}" for w in warnings)
            QMessageBox.critical(self, "Errore Configurazione", text)
        elif warnings:
            text = "<b>Avvisi configurazione:</b><br>" + "<br>".join(f"- {w}" for w in warnings)
            QMessageBox.warning(self, "Configurazione Incompleta", text)


def run_app(vision_learner=None, telegram_learner=None,
            rpa_healer=None, logger=None, executor=None):
    """Entry point per l'applicazione desktop."""
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    window = MainWindow(vision_learner, telegram_learner, rpa_healer, logger, executor)
    window.show()

    return app.exec()
