"""
Telegram Tab - Monitor and manage Telegram integration
All heavy operations (API calls, parsing) run in separate QThreads to avoid blocking UI.
"""
import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton,
    QLabel, QLineEdit, QGroupBox, QTableWidget, QTableWidgetItem,
    QCheckBox, QMessageBox, QSpinBox, QProgressBar
)
from PySide6.QtCore import Qt, Signal, QThread
from PySide6.QtGui import QFont
from datetime import datetime




class TelegramParseWorker(QThread):
    """Worker thread for parsing a single message with AI (avoids blocking UI)"""
    finished = Signal(str, str, object)  # timestamp, message, result (dict or None)

    def __init__(self, telegram_learner, message, timestamp=None):
        super().__init__()
        self.telegram_learner = telegram_learner
        self.message = message
        self.timestamp = timestamp or datetime.now().strftime("%H:%M:%S")

    def run(self):
        try:
            result = self.telegram_learner.parse_message(self.message)
            self.finished.emit(self.timestamp, self.message, result)
        except Exception:
            self.finished.emit(self.timestamp, self.message, None)


class TelegramListenerThread(QThread):
    """Thread for running Telegram listener via Telethon"""
    message_received = Signal(str, str)  # timestamp, message
    signal_parsed = Signal(object)  # parsed signal dict (for executor sync)
    status_changed = Signal(str)  # status
    error_occurred = Signal(str)  # error message

    def __init__(self, api_id, api_hash, agent, parser, logger):
        super().__init__()
        self.api_id = api_id
        self.api_hash = api_hash
        self.agent = agent
        self.parser = parser
        self.logger = logger
        self.running = True
        self.client = None  # Keep reference for clean disconnect
        self._loop = None

    def run(self):
        try:
            from telethon import TelegramClient, events
            import asyncio

            self.status_changed.emit("Connecting...")

            # EXE-safe absolute session path in data/ folder
            _base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            _data_dir = os.path.join(_base, "data")
            os.makedirs(_data_dir, exist_ok=True)
            session_path = os.path.join(_data_dir, f"session_{self.api_id}")
            self.client = TelegramClient(session_path, self.api_id, self.api_hash)
            client = self.client
            signal_ref = self.message_received
            signal_parsed_ref = self.signal_parsed
            parser_ref = self.parser
            logger_ref = self.logger

            async def main():
                @client.on(events.NewMessage)
                async def handler(event):
                    text = event.message.message
                    if not text:
                        return

                    ts = datetime.now().strftime("%H:%M:%S")
                    # Emit signal to UI thread (Qt signals are thread-safe)
                    signal_ref.emit(ts, text)

                    # Parse in this background thread (does NOT block UI)
                    try:
                        result = parser_ref.parse(text)
                        if result:
                            if logger_ref:
                                logger_ref.info(f"Parsed signal: {result}")
                            # Emit parsed signal via Qt Signal for thread-safe executor access
                            signal_parsed_ref.emit(result)
                    except Exception as e:
                        if logger_ref:
                            logger_ref.error(f"Parse error in listener: {e}")

                await client.start()
                if logger_ref:
                    logger_ref.info("Telegram listener connected successfully")
                self.status_changed.emit("Connected")
                await client.run_until_disconnected()

            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            self._loop.run_until_complete(main())

        except ImportError:
            self.error_occurred.emit("Telethon not installed. Run: pip install telethon")
        except Exception as e:
            self.error_occurred.emit(f"Telegram error: {str(e)}")
            self.status_changed.emit("Disconnected")
        finally:
            if self._loop and not self._loop.is_closed():
                self._loop.close()

    def stop(self):
        """Cleanly disconnect Telethon client and stop the thread."""
        self.running = False
        if self.client and self._loop and not self._loop.is_closed():
            try:
                import asyncio
                # Schedule disconnect on the event loop
                future = asyncio.run_coroutine_threadsafe(
                    self.client.disconnect(), self._loop
                )
                future.result(timeout=5)
            except Exception:
                pass  # Client may already be disconnected


class TelegramTab(QWidget):
    """Telegram integration tab"""
    # Widget-level signal: emitted when a valid signal is parsed (for MainWindow routing)
    signal_received = Signal(dict)

    def __init__(self, agent=None, telegram_learner=None, logger=None,
                 parent=None, executor=None, monitor=None, controller=None):
        super().__init__(parent)
        self.agent = agent
        self.telegram_learner = telegram_learner
        self.logger = logger
        self.executor = executor  # Shared singleton executor for signal handling
        self.monitor = monitor   # HealthMonitor for heartbeat
        self.controller = controller
        self.listener_thread = None
        self._parse_workers = []  # Keep references to active workers
        self.init_ui()

        # Load saved credentials from vault
        if self.controller:
            saved = self.controller.current_config
            if saved:
                self.api_id_input.setText(saved.get("api_id", ""))
                self.api_hash_input.setText(saved.get("api_hash", ""))
                self.phone_input.setText(saved.get("bot_token", ""))

    def init_ui(self):
        layout = QVBoxLayout(self)

        # Title
        title = QLabel("Telegram Integration")
        title.setFont(QFont("Arial", 16, QFont.Bold))
        layout.addWidget(title)

        # Connection settings
        settings_group = QGroupBox("Connection Settings")
        settings_layout = QVBoxLayout(settings_group)

        # API ID
        api_id_layout = QHBoxLayout()
        api_id_layout.addWidget(QLabel("API ID:"))
        self.api_id_input = QLineEdit()
        self.api_id_input.setPlaceholderText("Get from https://my.telegram.org")
        api_id_layout.addWidget(self.api_id_input)
        settings_layout.addLayout(api_id_layout)

        # API Hash
        api_hash_layout = QHBoxLayout()
        api_hash_layout.addWidget(QLabel("API Hash:"))
        self.api_hash_input = QLineEdit()
        self.api_hash_input.setEchoMode(QLineEdit.Password)
        self.api_hash_input.setPlaceholderText("API Hash from my.telegram.org")
        api_hash_layout.addWidget(self.api_hash_input)
        settings_layout.addLayout(api_hash_layout)

        # Phone
        phone_layout = QHBoxLayout()
        phone_layout.addWidget(QLabel("Phone:"))
        self.phone_input = QLineEdit()
        self.phone_input.setPlaceholderText("+39...")
        phone_layout.addWidget(self.phone_input)
        settings_layout.addLayout(phone_layout)

        layout.addWidget(settings_group)

        # Status
        status_group = QGroupBox("Status")
        status_layout = QVBoxLayout(status_group)

        self.status_label = QLabel("Status: <b style='color: gray;'>Disconnected</b>")
        self.messages_count_label = QLabel("Messages received: 0")
        self.parsed_count_label = QLabel("Successfully parsed: 0")

        status_layout.addWidget(self.status_label)
        status_layout.addWidget(self.messages_count_label)
        status_layout.addWidget(self.parsed_count_label)

        layout.addWidget(status_group)

        # Messages table
        messages_group = QGroupBox("Recent Messages")
        messages_layout = QVBoxLayout(messages_group)

        self.messages_table = QTableWidget()
        self.messages_table.setColumnCount(3)
        self.messages_table.setHorizontalHeaderLabels(["Time", "Message Preview", "Parsed"])
        self.messages_table.horizontalHeader().setStretchLastSection(True)
        self.messages_table.setMaximumHeight(200)

        messages_layout.addWidget(self.messages_table)

        layout.addWidget(messages_group)

        # Learning settings
        learning_group = QGroupBox("Auto-Learning Settings")
        learning_layout = QVBoxLayout(learning_group)

        self.auto_learn_check = QCheckBox("Enable auto-learning from messages")
        self.auto_learn_check.setChecked(True)

        min_examples_layout = QHBoxLayout()
        min_examples_layout.addWidget(QLabel("Learn after:"))
        self.min_examples_spin = QSpinBox()
        self.min_examples_spin.setRange(1, 10)
        self.min_examples_spin.setValue(3)
        min_examples_layout.addWidget(self.min_examples_spin)
        min_examples_layout.addWidget(QLabel("examples"))
        min_examples_layout.addStretch()

        learning_layout.addWidget(self.auto_learn_check)
        learning_layout.addLayout(min_examples_layout)

        layout.addWidget(learning_group)

        # Control buttons
        control_layout = QHBoxLayout()

        self.connect_btn = QPushButton("Connect")
        self.connect_btn.setStyleSheet("background-color: #4CAF50; color: white; padding: 10px;")
        self.connect_btn.clicked.connect(self.connect_telegram)

        self.disconnect_btn = QPushButton("Disconnect")
        self.disconnect_btn.setEnabled(False)
        self.disconnect_btn.setStyleSheet("background-color: #f44336; color: white; padding: 10px;")
        self.disconnect_btn.clicked.connect(self.disconnect_telegram)

        self.test_btn = QPushButton("Test Parser")
        self.test_btn.clicked.connect(self.test_parser)

        control_layout.addWidget(self.connect_btn)
        control_layout.addWidget(self.disconnect_btn)
        control_layout.addWidget(self.test_btn)
        control_layout.addStretch()

        layout.addLayout(control_layout)

        # Progress bar for parsing (hidden by default)
        self.parse_progress = QProgressBar()
        self.parse_progress.setRange(0, 0)  # indeterminate
        self.parse_progress.setVisible(False)
        layout.addWidget(self.parse_progress)

        # Instructions
        info_label = QLabel(
            "<b>How to get Telegram API credentials:</b><br>"
            "1. Go to <a href='https://my.telegram.org'>https://my.telegram.org</a><br>"
            "2. Login with your phone<br>"
            "3. Go to 'API development tools'<br>"
            "4. Create an app and copy API ID and Hash"
        )
        info_label.setOpenExternalLinks(True)
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        # Counters
        self.messages_received = 0
        self.messages_parsed = 0

    def connect_telegram(self):
        """Connect to Telegram"""
        api_id = self.api_id_input.text().strip()
        api_hash = self.api_hash_input.text().strip()

        if not api_id or not api_hash:
            QMessageBox.warning(
                self,
                "Missing Credentials",
                "Please enter API ID and API Hash"
            )
            return

        try:
            api_id = int(api_id)
        except ValueError:
            QMessageBox.warning(self, "Invalid API ID", "API ID must be a number")
            return

        # Disable connect button
        self.connect_btn.setEnabled(False)
        self.disconnect_btn.setEnabled(True)

        # Create parser
        try:
            from core.signal_parser import TelegramSignalParser as SignalParser
        except ImportError:
            class SignalParser:
                def parse(self, text):
                    return None
        parser = SignalParser()

        # Start listener thread
        self.listener_thread = TelegramListenerThread(
            api_id,
            api_hash,
            self.agent,
            parser,
            self.logger
        )

        self.listener_thread.message_received.connect(self.on_message_received)
        self.listener_thread.status_changed.connect(self.on_status_changed)
        self.listener_thread.error_occurred.connect(self.on_error)

        # Emit parsed signals as widget-level signal_received for MainWindow routing
        # (routed through Controller via RPAWorker — single path, no duplication)
        self.listener_thread.signal_parsed.connect(
            lambda data: self.signal_received.emit(data) if isinstance(data, dict) else None
        )

        self.listener_thread.start()

    def disconnect_telegram(self):
        """Disconnect from Telegram with clean shutdown"""
        if self.listener_thread:
            self.listener_thread.stop()
            self.listener_thread.quit()
            self.listener_thread.wait(5000)
            self.listener_thread.deleteLater()
            self.listener_thread = None

        self.connect_btn.setEnabled(True)
        self.disconnect_btn.setEnabled(False)
        self.update_status("Disconnected", "gray")

    def on_message_received(self, timestamp, message):
        """Handle new message - adds to table immediately, parses in background thread"""
        # Heartbeat: prove Telegram thread is alive
        if self.monitor:
            self.monitor.heartbeat()
        self.messages_received += 1
        self.messages_count_label.setText(f"Messages received: {self.messages_received}")

        # Add to table immediately (no blocking)
        row = self.messages_table.rowCount()
        self.messages_table.insertRow(row)
        self.messages_table.setItem(row, 0, QTableWidgetItem(timestamp))
        preview = message[:50] + "..." if len(message) > 50 else message
        self.messages_table.setItem(row, 1, QTableWidgetItem(preview))
        self.messages_table.setItem(row, 2, QTableWidgetItem("Parsing..."))

        # Keep only last 20 messages
        if self.messages_table.rowCount() > 20:
            self.messages_table.removeRow(0)

        # Parse in background thread (does NOT block UI)
        if self.telegram_learner and self.auto_learn_check.isChecked():
            worker = TelegramParseWorker(self.telegram_learner, message, timestamp)
            worker.finished.connect(self._on_parse_finished)
            worker.finished.connect(lambda: self._cleanup_worker(worker))
            self._parse_workers.append(worker)
            worker.start()

    def _on_parse_finished(self, timestamp, message, result):
        """Handle parse result from background worker - update table row"""
        # Find the row by timestamp
        for row in range(self.messages_table.rowCount()):
            item = self.messages_table.item(row, 0)
            if item and item.text() == timestamp:
                if result:
                    self.messages_table.setItem(
                        row, 2, QTableWidgetItem(f"OK: {result.get('teams', 'N/A')}")
                    )
                    self.messages_parsed += 1
                    self.parsed_count_label.setText(f"Successfully parsed: {self.messages_parsed}")
                else:
                    self.messages_table.setItem(row, 2, QTableWidgetItem("Failed"))
                break

    def _cleanup_worker(self, worker):
        """Remove finished worker from list and schedule deletion"""
        if worker in self._parse_workers:
            self._parse_workers.remove(worker)
        worker.quit()
        worker.wait()
        worker.deleteLater()

    def on_status_changed(self, status):
        """Handle status change"""
        color = {
            "Connecting...": "orange",
            "Connected": "green",
            "Disconnected": "gray",
            "Error": "red"
        }.get(status, "gray")

        self.update_status(status, color)

    def on_error(self, error):
        """Handle error"""
        QMessageBox.critical(self, "Telegram Error", error)
        self.update_status("Error", "red")
        self.connect_btn.setEnabled(True)
        self.disconnect_btn.setEnabled(False)

    def update_status(self, status, color):
        """Update status label"""
        self.status_label.setText(f"Status: <b style='color: {color};'>{status}</b>")

    def test_parser(self):
        """Test message parser - runs in background thread to avoid blocking UI"""
        test_message = """
LIVE SIGNAL
Inter - Milan
HT: 2-1
BET: Under 3.5 Goals
Confidence: HIGH
"""

        if not self.telegram_learner:
            QMessageBox.warning(self, "Parser Not Available", "Telegram learner not initialized")
            return

        # Disable button and show progress
        self.test_btn.setEnabled(False)
        self.parse_progress.setVisible(True)

        worker = TelegramParseWorker(self.telegram_learner, test_message)
        worker.finished.connect(self._on_test_finished)
        worker.finished.connect(lambda: self._cleanup_worker(worker))
        self._parse_workers.append(worker)
        worker.start()

    def _on_test_finished(self, timestamp, message, result):
        """Handle test parse result from background worker"""
        self.test_btn.setEnabled(True)
        self.parse_progress.setVisible(False)

        if result:
            msg = "Parser Test Successful!\n\n"
            msg += f"Teams: {result.get('teams', 'N/A')}\n"
            msg += f"Market: {result.get('market', 'N/A')}\n"
            msg += f"Score: {result.get('score', 'N/A')}"
            QMessageBox.information(self, "Parser Test", msg)
        else:
            QMessageBox.warning(self, "Parser Test", "Failed to parse test message")

    def get_settings(self):
        """Get Telegram settings"""
        return {
            "api_id": self.api_id_input.text(),
            "api_hash": self.api_hash_input.text(),
            "phone": self.phone_input.text(),
            "auto_learn": self.auto_learn_check.isChecked(),
            "min_examples": self.min_examples_spin.value()
        }
