"""
SuperAgent Desktop App - PySide6 Multi-Tab UI
Production-grade: Signal routing, RPAWorker queue, ConfigValidator, Dark Theme.
"""
import os
import sys
import time
import queue
import threading
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QPushButton, QLabel, QLineEdit, QGroupBox, QTabWidget,
    QTableWidget, QTableWidgetItem, QCheckBox, QMessageBox, QSpinBox,
    QProgressBar, QComboBox, QFormLayout, QSplitter
)
from PySide6.QtCore import Qt, Signal, QThread, QTimer, Slot
from PySide6.QtGui import QFont, QColor, QPalette
from datetime import datetime

# Absolute base dir (EXE-safe)
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ---------------------------------------------------------------------------
#  Config Validator
# ---------------------------------------------------------------------------
class ConfigValidator:
    """Validate config.yaml at startup and report missing/invalid fields."""

    REQUIRED = {
        "openrouter.api_key": str,
        "rpa.pin": str,
    }

    @classmethod
    def validate(cls, config: dict, logger=None):
        errors = []
        for dotpath, expected_type in cls.REQUIRED.items():
            parts = dotpath.split(".")
            val = config
            for p in parts:
                if isinstance(val, dict):
                    val = val.get(p)
                else:
                    val = None
                    break
            if val is None or val == "":
                errors.append(f"Missing or empty: {dotpath}")
            elif not isinstance(val, expected_type):
                errors.append(f"Wrong type for {dotpath}: expected {expected_type.__name__}")
        if errors and logger:
            for e in errors:
                logger.warning(f"[ConfigValidator] {e}")
        return errors


# ---------------------------------------------------------------------------
#  AI Worker (background thread for chat)
# ---------------------------------------------------------------------------
class AIWorker(QThread):
    """Runs AI queries off the main thread."""
    response_ready = Signal(str)
    error_occurred = Signal(str)

    def __init__(self, vision_learner, prompt):
        super().__init__()
        self.vision = vision_learner
        self.prompt = prompt

    def run(self):
        try:
            result = self.vision.understand_text(self.prompt, context="User chat query")
            if result:
                import json
                self.response_ready.emit(json.dumps(result, indent=2, ensure_ascii=False))
            else:
                self.response_ready.emit("No response from AI.")
        except Exception as e:
            self.error_occurred.emit(str(e))


# ---------------------------------------------------------------------------
#  RPA Worker — thread-safe bet queue
# ---------------------------------------------------------------------------
class RPAWorker(QThread):
    """Processes betting signals from a thread-safe queue.
    Runs in its own thread so the UI never blocks."""
    bet_placed = Signal(dict)   # emitted after a bet attempt
    bet_error = Signal(str)     # emitted on failure

    def __init__(self, executor, logger=None):
        super().__init__()
        self._queue = queue.Queue()
        self._running = True
        self.executor = executor
        self.logger = logger

    # --- public API (called from any thread) ---
    def enqueue_bet(self, signal_data: dict):
        """Thread-safe: add a parsed signal to the processing queue."""
        self._queue.put(signal_data)
        if self.logger:
            self.logger.info(f"[RPAWorker] Signal enqueued: {signal_data.get('teams', 'N/A')}")

    def stop(self):
        self._running = False
        self._queue.put(None)  # sentinel to unblock .get()

    # --- internal loop ---
    def run(self):
        while self._running:
            try:
                item = self._queue.get(timeout=2)
            except queue.Empty:
                continue
            if item is None:
                break  # sentinel
            try:
                self._process_signal(item)
            except Exception as e:
                if self.logger:
                    self.logger.error(f"[RPAWorker] Error processing signal: {e}")
                self.bet_error.emit(str(e))

    def _process_signal(self, signal_data: dict):
        if not self.executor:
            self.bet_error.emit("Executor not available")
            return
        teams = signal_data.get("teams", "")
        market = signal_data.get("market", "")
        if self.logger:
            self.logger.info(f"[RPAWorker] Processing: {teams} / {market}")

        selectors = self.executor._load_selectors()

        # 1. Ensure login
        if not self.executor.ensure_login(selectors):
            self.bet_error.emit("Login failed")
            return

        # 2. Navigate to match
        if teams and not self.executor.navigate_to_match(teams, selectors):
            self.bet_error.emit(f"Could not find match: {teams}")
            return

        # 3. Select market
        if market and not self.executor.select_market(market, selectors):
            self.bet_error.emit(f"Could not select market: {market}")
            return

        # 4. Place bet
        result = self.executor.place_bet(selectors)
        signal_data["placed"] = result
        signal_data["timestamp"] = datetime.now().isoformat()
        self.bet_placed.emit(signal_data)


# ---------------------------------------------------------------------------
#  Chat Tab
# ---------------------------------------------------------------------------
class ChatTab(QWidget):
    def __init__(self, vision_learner=None, logger=None, parent=None):
        super().__init__(parent)
        self.vision = vision_learner
        self.logger = logger
        self._workers = []
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        title = QLabel("AI Chat")
        title.setFont(QFont("Arial", 16, QFont.Bold))
        layout.addWidget(title)

        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        layout.addWidget(self.chat_display)

        input_layout = QHBoxLayout()
        self.chat_input = QLineEdit()
        self.chat_input.setPlaceholderText("Ask AI something...")
        self.chat_input.returnPressed.connect(self.send_message)
        self.send_btn = QPushButton("Send")
        self.send_btn.clicked.connect(self.send_message)
        input_layout.addWidget(self.chat_input)
        input_layout.addWidget(self.send_btn)
        layout.addLayout(input_layout)

    def send_message(self):
        text = self.chat_input.text().strip()
        if not text:
            return
        self.chat_display.append(f"<b>You:</b> {text}")
        self.chat_input.clear()

        if not self.vision:
            self.chat_display.append("<i>AI not available.</i>")
            return

        self.send_btn.setEnabled(False)
        worker = AIWorker(self.vision, text)
        worker.response_ready.connect(self._on_response)
        worker.error_occurred.connect(self._on_error)
        worker.finished.connect(lambda: self._cleanup_worker(worker))
        self._workers.append(worker)
        worker.start()

    def _on_response(self, text):
        self.chat_display.append(f"<b>AI:</b><pre>{text}</pre>")
        self.send_btn.setEnabled(True)

    def _on_error(self, err):
        self.chat_display.append(f"<span style='color:red;'>Error: {err}</span>")
        self.send_btn.setEnabled(True)

    def _cleanup_worker(self, w):
        if w in self._workers:
            self._workers.remove(w)
        w.deleteLater()


# ---------------------------------------------------------------------------
#  RPA Monitor Tab
# ---------------------------------------------------------------------------
class RPAMonitorTab(QWidget):
    def __init__(self, executor=None, rpa_worker=None, logger=None, parent=None):
        super().__init__(parent)
        self.executor = executor
        self.rpa_worker = rpa_worker
        self.logger = logger
        self._init_ui()

        if self.rpa_worker:
            self.rpa_worker.bet_placed.connect(self._on_bet_placed)
            self.rpa_worker.bet_error.connect(self._on_bet_error)

    def _init_ui(self):
        layout = QVBoxLayout(self)
        title = QLabel("RPA Monitor")
        title.setFont(QFont("Arial", 16, QFont.Bold))
        layout.addWidget(title)

        # Status
        status_group = QGroupBox("Executor Status")
        sl = QVBoxLayout(status_group)
        self.status_label = QLabel("Status: Idle")
        self.bets_label = QLabel("Bets placed: 0")
        sl.addWidget(self.status_label)
        sl.addWidget(self.bets_label)
        layout.addWidget(status_group)

        # Bet log table
        log_group = QGroupBox("Bet Log")
        ll = QVBoxLayout(log_group)
        self.bet_table = QTableWidget()
        self.bet_table.setColumnCount(4)
        self.bet_table.setHorizontalHeaderLabels(["Time", "Teams", "Market", "Result"])
        self.bet_table.horizontalHeader().setStretchLastSection(True)
        ll.addWidget(self.bet_table)
        layout.addWidget(log_group)

        self._bet_count = 0

    def _on_bet_placed(self, data: dict):
        self._bet_count += 1
        self.bets_label.setText(f"Bets placed: {self._bet_count}")
        row = self.bet_table.rowCount()
        self.bet_table.insertRow(row)
        self.bet_table.setItem(row, 0, QTableWidgetItem(data.get("timestamp", "")))
        self.bet_table.setItem(row, 1, QTableWidgetItem(data.get("teams", "")))
        self.bet_table.setItem(row, 2, QTableWidgetItem(data.get("market", "")))
        placed = data.get("placed", False)
        self.bet_table.setItem(row, 3, QTableWidgetItem("OK" if placed else "FAILED"))

    def _on_bet_error(self, err: str):
        self.status_label.setText(f"Status: Error — {err}")


# ---------------------------------------------------------------------------
#  Statistics Tab
# ---------------------------------------------------------------------------
class StatsTab(QWidget):
    def __init__(self, telegram_learner=None, logger=None, parent=None):
        super().__init__(parent)
        self.telegram_learner = telegram_learner
        self.logger = logger
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        title = QLabel("Statistics")
        title.setFont(QFont("Arial", 16, QFont.Bold))
        layout.addWidget(title)

        self.stats_display = QTextEdit()
        self.stats_display.setReadOnly(True)
        layout.addWidget(self.stats_display)

        refresh_btn = QPushButton("Refresh Stats")
        refresh_btn.clicked.connect(self.refresh)
        layout.addWidget(refresh_btn)

    def refresh(self):
        lines = []
        if self.telegram_learner:
            stats = self.telegram_learner.get_statistics()
            lines.append("=== Telegram Learning ===")
            for k, v in stats.items():
                lines.append(f"  {k}: {v}")
        else:
            lines.append("Telegram learner not available.")

        # Heartbeat info
        try:
            import main as _main_mod
            elapsed = time.time() - _main_mod.last_heartbeat
            lines.append(f"\n=== Heartbeat ===")
            lines.append(f"  Last heartbeat: {elapsed:.0f}s ago")
        except Exception:
            pass

        self.stats_display.setPlainText("\n".join(lines))


# ---------------------------------------------------------------------------
#  Settings Tab
# ---------------------------------------------------------------------------
class SettingsTab(QWidget):
    def __init__(self, config=None, logger=None, parent=None):
        super().__init__(parent)
        self.config = config or {}
        self.logger = logger
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        title = QLabel("Settings")
        title.setFont(QFont("Arial", 16, QFont.Bold))
        layout.addWidget(title)

        form = QFormLayout()

        self.rpa_enabled = QCheckBox()
        self.rpa_enabled.setChecked(self.config.get("rpa", {}).get("enabled", False))
        form.addRow("RPA Enabled:", self.rpa_enabled)

        self.autobet = QCheckBox()
        self.autobet.setChecked(self.config.get("rpa", {}).get("autobet", False))
        form.addRow("Auto-bet:", self.autobet)

        self.pin_input = QLineEdit(self.config.get("rpa", {}).get("pin", "0503"))
        self.pin_input.setEchoMode(QLineEdit.Password)
        form.addRow("PIN:", self.pin_input)

        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["dark", "light"])
        self.theme_combo.setCurrentText(self.config.get("ui", {}).get("theme", "dark"))
        form.addRow("Theme:", self.theme_combo)

        layout.addLayout(form)

        save_btn = QPushButton("Save Settings")
        save_btn.clicked.connect(self.save_settings)
        layout.addWidget(save_btn)
        layout.addStretch()

    def save_settings(self):
        import yaml
        config_path = os.path.join(_BASE_DIR, "config", "config.yaml")
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f) or {}
            cfg.setdefault("rpa", {})["enabled"] = self.rpa_enabled.isChecked()
            cfg["rpa"]["autobet"] = self.autobet.isChecked()
            cfg["rpa"]["pin"] = self.pin_input.text()
            cfg.setdefault("ui", {})["theme"] = self.theme_combo.currentText()
            with open(config_path, "w", encoding="utf-8") as f:
                yaml.dump(cfg, f, default_flow_style=False)
            QMessageBox.information(self, "Settings", "Settings saved!")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save: {e}")

    def get_settings(self):
        return {
            "rpa_enabled": self.rpa_enabled.isChecked(),
            "autobet": self.autobet.isChecked(),
            "pin": self.pin_input.text(),
            "theme": self.theme_combo.currentText(),
        }


# ---------------------------------------------------------------------------
#  Main Window
# ---------------------------------------------------------------------------
class MainWindow(QMainWindow):
    """Central window — owns all tabs and coordinates signal routing."""

    def __init__(self, vision=None, telegram_learner=None, rpa_healer=None,
                 logger=None, executor=None, config=None):
        super().__init__()
        self.vision = vision
        self.telegram_learner = telegram_learner
        self.rpa_healer = rpa_healer
        self.logger = logger
        self.executor = executor
        self.config = config or {}

        self.setWindowTitle("SuperAgent H24")
        self.setMinimumSize(1100, 750)

        # --- RPA Worker (thread-safe bet queue) ---
        self.rpa_worker = None
        if self.executor:
            self.rpa_worker = RPAWorker(executor=self.executor, logger=self.logger)
            self.rpa_worker.start()

        # --- Tabs ---
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        # 1. Chat
        self.chat_tab = ChatTab(vision_learner=vision, logger=logger)
        self.tabs.addTab(self.chat_tab, "Chat")

        # 2. RPA Monitor
        self.rpa_tab = RPAMonitorTab(executor=executor, rpa_worker=self.rpa_worker, logger=logger)
        self.tabs.addTab(self.rpa_tab, "RPA Monitor")

        # 3. Telegram
        from ui.telegram_tab import TelegramTab
        self.telegram_tab = TelegramTab(
            agent=vision,
            telegram_learner=telegram_learner,
            logger=logger,
            executor=executor,
        )
        self.tabs.addTab(self.telegram_tab, "Telegram")

        # Connect Telegram parsed signals → our process_new_signal slot
        if hasattr(self.telegram_tab, 'listener_thread') and self.telegram_tab.listener_thread:
            self._connect_telegram_signals(self.telegram_tab.listener_thread)
        # Also monkey-patch TelegramTab.connect_telegram to hook future threads
        _orig_connect = self.telegram_tab.connect_telegram
        _self = self

        def _patched_connect():
            _orig_connect()
            if _self.telegram_tab.listener_thread:
                _self._connect_telegram_signals(_self.telegram_tab.listener_thread)
        self.telegram_tab.connect_telegram = _patched_connect

        # 4. Statistics
        self.stats_tab = StatsTab(telegram_learner=telegram_learner, logger=logger)
        self.tabs.addTab(self.stats_tab, "Statistics")

        # 5. Settings
        self.settings_tab = SettingsTab(config=self.config, logger=logger)
        self.tabs.addTab(self.settings_tab, "Settings")

        # --- Heartbeat timer (update UI with uptime) ---
        self._heartbeat_timer = QTimer(self)
        self._heartbeat_timer.timeout.connect(self._update_heartbeat)
        self._heartbeat_timer.start(10000)  # every 10 s

    def _connect_telegram_signals(self, listener_thread):
        """Wire a TelegramListenerThread's signal_parsed → process_new_signal."""
        try:
            listener_thread.signal_parsed.connect(self.process_new_signal)
        except Exception:
            pass  # already connected or thread not ready

    @Slot(object)
    def process_new_signal(self, data):
        """Receive a parsed signal from Telegram and enqueue it for RPA."""
        if self.logger:
            self.logger.info(f"[MainWindow] Received signal: {data}")
        if self.rpa_worker and data:
            try:
                self.rpa_worker.enqueue_bet(data)
            except Exception as e:
                if self.logger:
                    self.logger.error(f"[MainWindow] Error enqueuing signal: {e}")

    def _update_heartbeat(self):
        """Refresh heartbeat in main module (proves UI is alive)."""
        try:
            import main as _main_mod
            _main_mod.last_heartbeat = time.time()
        except Exception:
            pass

    def closeEvent(self, event):
        """Graceful shutdown on window close."""
        if self.logger:
            self.logger.info("MainWindow closing — shutting down workers...")

        # Stop RPA worker
        if self.rpa_worker:
            self.rpa_worker.stop()
            self.rpa_worker.quit()
            self.rpa_worker.wait(5000)

        # Disconnect Telegram
        if hasattr(self.telegram_tab, 'disconnect_telegram'):
            try:
                self.telegram_tab.disconnect_telegram()
            except Exception:
                pass

        # Close executor
        if self.executor:
            try:
                self.executor.close()
            except Exception:
                pass

        event.accept()


# ---------------------------------------------------------------------------
#  Dark Theme
# ---------------------------------------------------------------------------
def apply_dark_theme(app: QApplication):
    """Apply dark palette to the entire application."""
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(30, 30, 30))
    palette.setColor(QPalette.WindowText, QColor(220, 220, 220))
    palette.setColor(QPalette.Base, QColor(40, 40, 40))
    palette.setColor(QPalette.AlternateBase, QColor(50, 50, 50))
    palette.setColor(QPalette.ToolTipBase, QColor(50, 50, 50))
    palette.setColor(QPalette.ToolTipText, QColor(220, 220, 220))
    palette.setColor(QPalette.Text, QColor(220, 220, 220))
    palette.setColor(QPalette.Button, QColor(50, 50, 50))
    palette.setColor(QPalette.ButtonText, QColor(220, 220, 220))
    palette.setColor(QPalette.BrightText, QColor(255, 50, 50))
    palette.setColor(QPalette.Link, QColor(42, 130, 218))
    palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
    palette.setColor(QPalette.HighlightedText, QColor(0, 0, 0))
    app.setPalette(palette)
    app.setStyleSheet("""
        QTabWidget::pane { border: 1px solid #444; }
        QTabBar::tab { background: #333; color: #ddd; padding: 8px 16px; }
        QTabBar::tab:selected { background: #555; }
        QGroupBox { border: 1px solid #555; margin-top: 10px; padding-top: 10px; }
        QGroupBox::title { color: #aaa; }
        QPushButton { padding: 6px 12px; }
    """)


# ---------------------------------------------------------------------------
#  run_app  — entry point called from main.py
# ---------------------------------------------------------------------------
def run_app(vision=None, telegram_learner=None, rpa_healer=None,
            logger=None, executor=None, config=None):
    """Create QApplication, apply theme, show MainWindow, exec."""
    app = QApplication(sys.argv)
    app.setApplicationName("SuperAgent")

    # Apply dark theme by default
    apply_dark_theme(app)

    window = MainWindow(
        vision=vision,
        telegram_learner=telegram_learner,
        rpa_healer=rpa_healer,
        logger=logger,
        executor=executor,
        config=config,
    )
    window.show()
    return app.exec()
