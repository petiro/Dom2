"""
SuperAgent Desktop UI - Modern Interface
Combines AI learning, RPA automation, and desktop interface
"""
import sys
import os
import json
import yaml
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
    """Worker thread for RPA browser automation"""
    status_changed = Signal(str, str)  # status, color
    error_occurred = Signal(str)
    task_completed = Signal()

    def __init__(self, logger, headless=True):
        super().__init__()
        self.logger = logger
        self.headless = headless
        self.running = False
        self.executor = None

    def run(self):
        self.running = True
        try:
            from core.dom_executor_playwright import DomExecutorPlaywright
            self.executor = DomExecutorPlaywright(
                logger=self.logger,
                headless=self.headless,
                allow_place=False
            )
            self.status_changed.emit("RUNNING", "green")

            # Keep alive while running
            import time
            while self.running:
                time.sleep(1)

        except Exception as e:
            self.error_occurred.emit(f"RPA Error: {str(e)}")
        finally:
            if self.executor:
                self.executor.close()
            self.status_changed.emit("STOPPED", "gray")

    def stop(self):
        self.running = False


class RPAMonitorTab(QWidget):
    """RPA monitoring and control tab"""

    def __init__(self, logger=None, parent=None):
        super().__init__(parent)
        self.logger = logger
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

        self.rpa_worker = RPAWorker(logger=self.logger, headless=True)
        self.rpa_worker.status_changed.connect(self.on_status_changed)
        self.rpa_worker.error_occurred.connect(self.on_error)
        self.rpa_worker.task_completed.connect(self.on_task_completed)
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
        """Show info about healing feature"""
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
        """Load stats from telegram_learner and healing history"""
        # Telegram stats
        if self.telegram_learner:
            stats = self.telegram_learner.get_statistics()
            self.update_telegram_stats(
                stats.get("total_messages", 0),
                stats.get("active_patterns", 0),
                stats.get("success_rate", 0.0)
            )

        # RPA healing stats from file
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

        # API Configuration
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

        # RPA Settings
        rpa_group = QGroupBox("RPA Settings")
        rpa_layout = QVBoxLayout(rpa_group)

        self.autobet_check = QCheckBox("Enable Auto-Bet (USE WITH CAUTION)")
        self.headless_check = QCheckBox("Headless browser")
        self.headless_check.setChecked(True)

        rpa_layout.addWidget(self.autobet_check)
        rpa_layout.addWidget(self.headless_check)

        layout.addWidget(rpa_group)

        # Learning Settings
        learning_group = QGroupBox("Learning Settings")
        learning_layout = QVBoxLayout(learning_group)

        self.telegram_learning_check = QCheckBox("Enable Telegram Learning")
        self.telegram_learning_check.setChecked(True)

        self.rpa_healing_check = QCheckBox("Enable RPA Self-Healing")
        self.rpa_healing_check.setChecked(True)

        learning_layout.addWidget(self.telegram_learning_check)
        learning_layout.addWidget(self.rpa_healing_check)

        layout.addWidget(learning_group)

        # Save button
        save_btn = QPushButton("Save Settings")
        save_btn.setStyleSheet("background-color: #2196F3; color: white; padding: 10px; font-weight: bold;")
        save_btn.clicked.connect(self.save_settings)
        layout.addWidget(save_btn)

        layout.addStretch()

    def _load_current_settings(self):
        """Load current settings from config.yaml into the UI"""
        if not os.path.exists(self.config_path):
            return
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f) or {}

            # API key
            api_key = config.get("openrouter", {}).get("api_key", "")
            if api_key and api_key != "INSERISCI_KEY":
                self.api_key_input.setText(api_key)

            # Model
            model = config.get("openrouter", {}).get("model", "")
            idx = self.model_select.findText(model)
            if idx >= 0:
                self.model_select.setCurrentIndex(idx)

            # RPA
            rpa = config.get("rpa", {})
            self.autobet_check.setChecked(rpa.get("autobet", False))
            self.headless_check.setChecked(rpa.get("headless", True))

            # Learning
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
        """Save settings to config.yaml"""
        try:
            # Load existing config to preserve fields we don't edit
            config = {}
            if os.path.exists(self.config_path):
                with open(self.config_path, "r", encoding="utf-8") as f:
                    config = yaml.safe_load(f) or {}

            # Update values
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

            # Write
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


class MainWindow(QMainWindow):
    """Main application window"""

    def __init__(self, vision_learner=None, telegram_learner=None, agent=None, logger=None):
        super().__init__()
        self.vision = vision_learner
        self.telegram_learner = telegram_learner
        self.agent = agent
        self.logger = logger
        self.init_ui()

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_status)
        self.timer.start(1000)

        self.start_time = datetime.now()

    def init_ui(self):
        self.setWindowTitle("SuperAgent - Intelligent RPA Desktop")
        self.setGeometry(100, 100, 1200, 800)

        central = QWidget()
        self.setCentralWidget(central)

        layout = QVBoxLayout(central)

        header = QLabel("SuperAgent - Intelligent RPA System")
        header.setFont(QFont("Arial", 20, QFont.Bold))
        header.setAlignment(Qt.AlignCenter)
        header.setStyleSheet("background-color: #2196F3; color: white; padding: 15px; border-radius: 5px;")
        layout.addWidget(header)

        self.tabs = QTabWidget()

        self.chat_tab = ChatTab(self.vision)
        self.rpa_tab = RPAMonitorTab(logger=self.logger)
        self.telegram_tab = TelegramTab(self.agent, self.telegram_learner, self.logger)
        self.stats_tab = StatsTab(telegram_learner=self.telegram_learner)
        self.settings_tab = SettingsTab()

        self.tabs.addTab(self.chat_tab, "AI Chat")
        self.tabs.addTab(self.rpa_tab, "RPA Monitor")
        self.tabs.addTab(self.telegram_tab, "Telegram")
        self.tabs.addTab(self.stats_tab, "Statistics")
        self.tabs.addTab(self.settings_tab, "Settings")

        layout.addWidget(self.tabs)

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")

        self.apply_theme()

    def apply_theme(self):
        """Apply modern dark theme"""
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

        self.setPalette(palette)

    def update_status(self):
        """Update status bar with uptime"""
        uptime = datetime.now() - self.start_time
        self.status_bar.showMessage(f"Uptime: {uptime.seconds}s | Status: Ready")


def run_app(vision_learner=None, telegram_learner=None, agent=None, logger=None):
    """Run the desktop application"""
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    window = MainWindow(vision_learner, telegram_learner, agent, logger)
    window.show()

    return app.exec()
