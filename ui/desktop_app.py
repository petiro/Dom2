"""
SuperAgent Desktop App V4 - PySide6 Multi-Tab UI
Production-grade: Signal routing, RPAWorker queue, TrainerTab with memory,
Stealth slider, ConfigValidator, Dark Theme, Controller V4 signal wiring.
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
#  Trainer Worker — AI with memory context (for TrainerTab)
# ---------------------------------------------------------------------------
class TrainerWorker(QThread):
    """Runs AI trainer queries off the main thread with memory context."""
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
            result = self.controller.ask_trainer(
                self.question,
                include_dom=self.include_dom,
                include_screenshot=self.include_screenshot,
            )
            self.response_ready.emit(result or "Nessuna risposta.")
        except Exception as e:
            self.error_occurred.emit(str(e))


# ---------------------------------------------------------------------------
#  RPA Worker — thread-safe bet queue
# ---------------------------------------------------------------------------
class RPAWorker(QThread):
    """Processes betting signals from a thread-safe queue.
    V4: Routes ALL signals through Controller (single point of coordination).
    Runs in its own thread so the UI never blocks."""
    bet_placed = Signal(dict)   # emitted after a bet attempt
    bet_error = Signal(str)     # emitted on failure

    def __init__(self, executor, logger=None, monitor=None, controller=None):
        super().__init__()
        self._queue = queue.Queue()
        self._running = True
        self.executor = executor
        self.logger = logger
        self.monitor = monitor  # HealthMonitor for heartbeat
        self.controller = controller  # V4: Central orchestrator

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
        teams = signal_data.get("teams", "")
        market = signal_data.get("market", "")
        if self.logger:
            self.logger.info(f"[RPAWorker] Processing: {teams} / {market}")

        # V4: Route through Controller (single point of coordination)
        if self.controller:
            result = self.controller.handle_signal(signal_data)
            signal_data["placed"] = result
            signal_data["timestamp"] = datetime.now().isoformat()
            if result:
                self.bet_placed.emit(signal_data)
            else:
                self.bet_error.emit(f"Signal failed: {teams} / {market}")
            return

        # Fallback: direct executor (legacy compat, should not happen in V4)
        if not self.executor:
            self.bet_error.emit("Executor not available")
            return
        if self.monitor:
            self.monitor.heartbeat()

        selectors = self.executor._load_selectors()
        if not self.executor.ensure_login(selectors):
            self.bet_error.emit("Login failed")
            return
        if teams and not self.executor.navigate_to_match(teams, selectors):
            self.bet_error.emit(f"Could not find match: {teams}")
            return
        if market and not self.executor.select_market(market, selectors):
            self.bet_error.emit(f"Could not select market: {market}")
            return
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
#  Trainer Tab — AI Chat with Memory + DOM/Screenshot context
# ---------------------------------------------------------------------------
class TrainerTab(QWidget):
    """AI Trainer with conversation memory and optional DOM/Screenshot context."""

    def __init__(self, controller=None, logger=None, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.logger = logger
        self._workers = []
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        title = QLabel("AI Trainer")
        title.setFont(QFont("Arial", 16, QFont.Bold))
        layout.addWidget(title)

        # Chat display
        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        self.chat_display.setStyleSheet("QTextEdit { font-family: 'Consolas', monospace; }")
        layout.addWidget(self.chat_display)

        # Context options
        ctx_layout = QHBoxLayout()
        self.include_dom = QCheckBox("Includi DOM")
        self.include_dom.setToolTip("Allega snapshot DOM della pagina corrente")
        ctx_layout.addWidget(self.include_dom)

        self.include_screenshot = QCheckBox("Includi Screenshot")
        self.include_screenshot.setToolTip("Allega screenshot della pagina corrente")
        ctx_layout.addWidget(self.include_screenshot)

        self.clear_memory_btn = QPushButton("Cancella Memoria")
        self.clear_memory_btn.clicked.connect(self._clear_memory)
        ctx_layout.addWidget(self.clear_memory_btn)

        # V4: Train Step button
        self.train_btn = QPushButton("Train Step")
        self.train_btn.setToolTip("Esegui un ciclo completo di training (Snapshot+Vision+LLM)")
        self.train_btn.clicked.connect(self._on_train_step)
        ctx_layout.addWidget(self.train_btn)

        ctx_layout.addStretch()
        layout.addLayout(ctx_layout)

        # Input
        input_layout = QHBoxLayout()
        self.chat_input = QLineEdit()
        self.chat_input.setPlaceholderText("Chiedi all'AI Trainer (con memoria)...")
        self.chat_input.returnPressed.connect(self.send_message)
        self.send_btn = QPushButton("Invia")
        self.send_btn.clicked.connect(self.send_message)
        input_layout.addWidget(self.chat_input)
        input_layout.addWidget(self.send_btn)
        layout.addLayout(input_layout)

        # Memory indicator
        self.memory_label = QLabel("Memoria: 0 messaggi")
        self.memory_label.setStyleSheet("color: #888;")
        layout.addWidget(self.memory_label)

    def send_message(self):
        text = self.chat_input.text().strip()
        if not text:
            return
        self.chat_display.append(f"<b>Tu:</b> {text}")
        self.chat_input.clear()

        if not self.controller:
            self.chat_display.append("<i>Controller non disponibile.</i>")
            return

        self.send_btn.setEnabled(False)
        worker = TrainerWorker(
            self.controller, text,
            include_dom=self.include_dom.isChecked(),
            include_screenshot=self.include_screenshot.isChecked(),
        )
        worker.response_ready.connect(self._on_response)
        worker.error_occurred.connect(self._on_error)
        worker.finished.connect(lambda: self._cleanup_worker(worker))
        self._workers.append(worker)
        worker.start()

    def _on_response(self, text):
        self.chat_display.append(f"<b>AI Trainer:</b><pre>{text}</pre>")
        self.send_btn.setEnabled(True)
        self._update_memory_label()

    def _on_error(self, err):
        self.chat_display.append(f"<span style='color:red;'>Errore: {err}</span>")
        self.send_btn.setEnabled(True)

    def _cleanup_worker(self, w):
        if w in self._workers:
            self._workers.remove(w)
        w.deleteLater()

    def _clear_memory(self):
        if self.controller:
            self.controller.clear_trainer_memory()
        self.chat_display.append("<i>--- Memoria conversazione cancellata ---</i>")
        self._update_memory_label()

    def _on_train_step(self):
        """Trigger V4 training step via controller."""
        if self.controller:
            self.train_btn.setEnabled(False)
            self.chat_display.append("<i>Training step in corso...</i>")
            self.controller.request_training()

    @Slot(str)
    def on_training_complete(self, result: str):
        """Called when controller emits training_complete signal."""
        self.chat_display.append(f"<b>Training Result:</b><pre>{result}</pre>")
        self.train_btn.setEnabled(True)
        self._update_memory_label()

    def _update_memory_label(self):
        if self.controller and self.controller.trainer:
            count = len(self.controller.trainer.memory)
            self.memory_label.setText(f"Memoria: {count} messaggi")
        else:
            self.memory_label.setText("Memoria: N/A")


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
    def __init__(self, telegram_learner=None, logger=None, monitor=None,
                 controller=None, parent=None):
        super().__init__(parent)
        self.telegram_learner = telegram_learner
        self.logger = logger
        self.monitor = monitor
        self.controller = controller
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

        # Controller stats
        if self.controller:
            cstats = self.controller.get_stats()
            lines.append(f"\n=== Controller V4 ===")
            lines.append(f"  State: {cstats.get('state', 'N/A')}")
            lines.append(f"  Signals received: {cstats.get('signals_received', 0)}")
            lines.append(f"  Bets total: {cstats.get('bets_total', 0)}")
            lines.append(f"  Bets placed: {cstats.get('bets_placed', 0)}")
            lines.append(f"  Bets failed: {cstats.get('bets_failed', 0)}")
            uptime_h = cstats.get('uptime_s', 0) / 3600
            lines.append(f"  Uptime: {uptime_h:.1f}h")

        # HealthMonitor info
        if self.monitor:
            elapsed = time.time() - self.monitor.last_heartbeat
            uptime = time.time() - self.monitor.start_time.timestamp()
            lines.append(f"\n=== Health Monitor ===")
            lines.append(f"  Last heartbeat: {elapsed:.0f}s ago")
            lines.append(f"  Uptime: {uptime/3600:.1f}h")
            lines.append(f"  Internet: {'OK' if self.monitor.internet_alive(2) else 'OFFLINE'}")
            if self.monitor._mem_samples:
                avg = sum(self.monitor._mem_samples) / len(self.monitor._mem_samples)
                lines.append(f"  Memory avg: {avg:.0f} MB")
        else:
            try:
                import main as _main_mod
                elapsed = time.time() - _main_mod.last_heartbeat
                lines.append(f"\n=== Heartbeat ===")
                lines.append(f"  Last heartbeat: {elapsed:.0f}s ago")
            except Exception:
                pass

        self.stats_display.setPlainText("\n".join(lines))


# ---------------------------------------------------------------------------
#  Settings Tab (with Stealth slider)
# ---------------------------------------------------------------------------
class SettingsTab(QWidget):
    stealth_changed = Signal(str)  # emitted when stealth mode changes

    def __init__(self, config=None, logger=None, controller=None, parent=None):
        super().__init__(parent)
        self.config = config or {}
        self.logger = logger
        self.controller = controller
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

        # --- Stealth Mode Slider ---
        self.stealth_combo = QComboBox()
        self.stealth_combo.addItems(["Umano Lento", "Bilanciato", "Pro (Live Mode)"])
        # Map display names to internal keys
        stealth_map = {"slow": 0, "balanced": 1, "pro": 2}
        current_stealth = self.config.get("rpa", {}).get("stealth_mode", "balanced")
        self.stealth_combo.setCurrentIndex(stealth_map.get(current_stealth, 1))
        self.stealth_combo.currentIndexChanged.connect(self._on_stealth_changed)
        form.addRow("Stealth Mode:", self.stealth_combo)

        layout.addLayout(form)

        save_btn = QPushButton("Save Settings")
        save_btn.clicked.connect(self.save_settings)
        layout.addWidget(save_btn)
        layout.addStretch()

    def _stealth_key(self) -> str:
        """Convert combo index to internal stealth key."""
        return ["slow", "balanced", "pro"][self.stealth_combo.currentIndex()]

    def _on_stealth_changed(self, index):
        mode = ["slow", "balanced", "pro"][index]
        self.stealth_changed.emit(mode)
        if self.controller:
            self.controller.set_stealth_mode(mode)

    def save_settings(self):
        import yaml
        config_path = os.path.join(_BASE_DIR, "config", "config.yaml")
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f) or {}
            cfg.setdefault("rpa", {})["enabled"] = self.rpa_enabled.isChecked()
            cfg["rpa"]["autobet"] = self.autobet.isChecked()
            cfg["rpa"]["pin"] = self.pin_input.text()
            cfg["rpa"]["stealth_mode"] = self._stealth_key()
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
            "stealth_mode": self._stealth_key(),
        }


# ---------------------------------------------------------------------------
#  Main Window
# ---------------------------------------------------------------------------
class MainWindow(QMainWindow):
    """Central window — owns all tabs and coordinates signal routing."""

    def __init__(self, vision=None, telegram_learner=None, rpa_healer=None,
                 logger=None, executor=None, config=None, monitor=None,
                 controller=None):
        super().__init__()
        self.vision = vision
        self.telegram_learner = telegram_learner
        self.rpa_healer = rpa_healer
        self.logger = logger
        self.executor = executor
        self.config = config or {}
        self.monitor = monitor  # HealthMonitor
        self.controller = controller  # SuperAgentController V4

        self.setWindowTitle("SuperAgent H24 V4")
        self.setMinimumSize(1100, 750)

        # --- RPA Worker (thread-safe bet queue, routes through Controller) ---
        self.rpa_worker = None
        if self.executor or self.controller:
            self.rpa_worker = RPAWorker(
                executor=self.executor, logger=self.logger,
                monitor=self.monitor, controller=self.controller,
            )
            self.rpa_worker.start()

        # --- Tabs ---
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        # 1. Chat
        self.chat_tab = ChatTab(vision_learner=vision, logger=logger)
        self.tabs.addTab(self.chat_tab, "Chat")

        # 2. AI Trainer (with memory)
        self.trainer_tab = TrainerTab(controller=self.controller, logger=logger)
        self.tabs.addTab(self.trainer_tab, "AI Trainer")

        # 3. RPA Monitor
        self.rpa_tab = RPAMonitorTab(executor=executor, rpa_worker=self.rpa_worker, logger=logger)
        self.tabs.addTab(self.rpa_tab, "RPA Monitor")

        # 4. Telegram
        from ui.telegram_tab import TelegramTab
        self.telegram_tab = TelegramTab(
            agent=vision,
            telegram_learner=telegram_learner,
            logger=logger,
            executor=executor,
            monitor=self.monitor,
        )
        self.tabs.addTab(self.telegram_tab, "Telegram")

        # Connect TelegramTab's widget-level signal_received -> process_new_signal
        self.telegram_tab.signal_received.connect(self.process_new_signal)

        # 5. Statistics
        self.stats_tab = StatsTab(
            telegram_learner=telegram_learner, logger=logger,
            monitor=self.monitor, controller=self.controller,
        )
        self.tabs.addTab(self.stats_tab, "Statistics")

        # 6. Settings (with stealth slider)
        self.settings_tab = SettingsTab(
            config=self.config, logger=logger, controller=self.controller,
        )
        self.tabs.addTab(self.settings_tab, "Settings")

        # Connect stealth mode changes to executor
        self.settings_tab.stealth_changed.connect(self._on_stealth_changed)

        # --- V4: Controller signal wiring ---
        if self.controller:
            # Wire controller.log_message -> log display
            self.controller.log_message.connect(self._on_controller_log)
            # Wire controller.training_complete -> trainer tab
            self.controller.training_complete.connect(self.trainer_tab.on_training_complete)
            # Wire state_manager.state_changed -> status bar update
            self.controller.state_manager.state_changed.connect(self._on_state_changed)

        # --- Heartbeat timer (update UI with uptime) ---
        self._heartbeat_timer = QTimer(self)
        self._heartbeat_timer.timeout.connect(self._update_heartbeat)
        self._heartbeat_timer.start(10000)  # every 10 s

        # --- State label in status bar ---
        self._state_label = QLabel("State: BOOT")
        self.statusBar().addPermanentWidget(self._state_label)

        # --- V4: Controller log display in status bar ---
        self._log_label = QLabel("")
        self._log_label.setStyleSheet("color: #888; font-size: 11px;")
        self.statusBar().addWidget(self._log_label, 1)

    # ------------------------------------------------------------------
    #  V4: Controller signal handlers
    # ------------------------------------------------------------------
    @Slot(str)
    def _on_controller_log(self, msg: str):
        """Display controller log messages in status bar."""
        self._log_label.setText(msg)

    @Slot(object)
    def _on_state_changed(self, new_state):
        """Update status bar when agent state changes."""
        self._state_label.setText(f"State: {new_state.name}")

    @Slot(str)
    def _on_stealth_changed(self, mode: str):
        if self.executor and hasattr(self.executor, 'stealth_mode'):
            self.executor.stealth_mode = mode
        if self.logger:
            self.logger.info(f"[UI] Stealth mode changed to: {mode}")

    @Slot(dict)
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
        """Refresh heartbeat via HealthMonitor (proves UI is alive)."""
        if self.monitor:
            self.monitor.heartbeat()
        # Backward compat: also update main.last_heartbeat directly
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

        # Shutdown controller
        if self.controller:
            try:
                self.controller.shutdown()
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
#  run_app  — entry point called from main.py (backward compat)
# ---------------------------------------------------------------------------
def run_app(vision=None, telegram_learner=None, rpa_healer=None,
            logger=None, executor=None, config=None, monitor=None,
            controller=None):
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
        monitor=monitor,
        controller=controller,
    )
    window.show()
    return app.exec()
