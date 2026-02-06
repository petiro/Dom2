"""
Telegram Tab - Monitor and manage Telegram integration
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton,
    QLabel, QLineEdit, QGroupBox, QTableWidget, QTableWidgetItem,
    QCheckBox, QMessageBox, QSpinBox
)
from PySide6.QtCore import Qt, Signal, QThread
from PySide6.QtGui import QFont
from datetime import datetime


class TelegramListenerThread(QThread):
    """Thread for running Telegram listener"""
    message_received = Signal(str, str)  # timestamp, message
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
        self.listener = None
    
    def run(self):
        try:
            from gateway.telegram_listener_fixed import TelegramListener
            
            self.status_changed.emit("Connecting...")
            
            # Create listener
            self.listener = TelegramListener(
                self.api_id,
                self.api_hash,
                self.agent,
                self.parser,
                self.logger
            )
            
            self.status_changed.emit("Connected")
            
            # Start listening (this blocks)
            import asyncio
            asyncio.run(self.listener.start())
            
        except ImportError:
            self.error_occurred.emit("Telethon not installed. Run: pip install telethon")
        except Exception as e:
            self.error_occurred.emit(f"Telegram error: {str(e)}")
            self.status_changed.emit("Disconnected")
    
    def stop(self):
        self.running = False
        if self.listener:
            # Stop listener gracefully
            pass


class TelegramTab(QWidget):
    """Telegram integration tab"""
    
    def __init__(self, agent=None, telegram_learner=None, logger=None, parent=None):
        super().__init__(parent)
        self.agent = agent
        self.telegram_learner = telegram_learner
        self.logger = logger
        self.listener_thread = None
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # Title
        title = QLabel("📱 Telegram Integration")
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
        
        self.connect_btn = QPushButton("🔌 Connect")
        self.connect_btn.setStyleSheet("background-color: #4CAF50; color: white; padding: 10px;")
        self.connect_btn.clicked.connect(self.connect_telegram)
        
        self.disconnect_btn = QPushButton("🔌 Disconnect")
        self.disconnect_btn.setEnabled(False)
        self.disconnect_btn.setStyleSheet("background-color: #f44336; color: white; padding: 10px;")
        self.disconnect_btn.clicked.connect(self.disconnect_telegram)
        
        self.test_btn = QPushButton("🧪 Test Parser")
        self.test_btn.clicked.connect(self.test_parser)
        
        control_layout.addWidget(self.connect_btn)
        control_layout.addWidget(self.disconnect_btn)
        control_layout.addWidget(self.test_btn)
        control_layout.addStretch()
        
        layout.addLayout(control_layout)
        
        # Instructions
        info_label = QLabel(
            "ℹ️ <b>How to get Telegram API credentials:</b><br>"
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
        from gateway.telegram_parser_fixed import TelegramParser
        parser = TelegramParser(self.logger, api_key=None)  # Will use telegram_learner
        
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
        
        self.listener_thread.start()
    
    def disconnect_telegram(self):
        """Disconnect from Telegram"""
        if self.listener_thread:
            self.listener_thread.stop()
            self.listener_thread.wait()
        
        self.connect_btn.setEnabled(True)
        self.disconnect_btn.setEnabled(False)
        self.update_status("Disconnected", "gray")
    
    def on_message_received(self, timestamp, message):
        """Handle new message"""
        self.messages_received += 1
        self.messages_count_label.setText(f"Messages received: {self.messages_received}")
        
        # Try to parse
        parsed = "❌ Failed"
        if self.telegram_learner and self.auto_learn_check.isChecked():
            result = self.telegram_learner.parse_message(message)
            if result:
                parsed = f"✅ {result.get('teams', 'N/A')}"
                self.messages_parsed += 1
                self.parsed_count_label.setText(f"Successfully parsed: {self.messages_parsed}")
        
        # Add to table
        row = self.messages_table.rowCount()
        self.messages_table.insertRow(row)
        
        self.messages_table.setItem(row, 0, QTableWidgetItem(timestamp))
        
        preview = message[:50] + "..." if len(message) > 50 else message
        self.messages_table.setItem(row, 1, QTableWidgetItem(preview))
        
        self.messages_table.setItem(row, 2, QTableWidgetItem(parsed))
        
        # Keep only last 20 messages
        if self.messages_table.rowCount() > 20:
            self.messages_table.removeRow(0)
    
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
        """Test message parser"""
        test_message = """
🔥 LIVE SIGNAL
⚽ Inter - Milan
📊 HT: 2-1
💰 BET: Under 3.5 Goals
🎯 Confidence: HIGH
"""
        
        if not self.telegram_learner:
            QMessageBox.warning(self, "Parser Not Available", "Telegram learner not initialized")
            return
        
        result = self.telegram_learner.parse_message(test_message)
        
        if result:
            msg = "✅ Parser Test Successful!\n\n"
            msg += f"Teams: {result.get('teams', 'N/A')}\n"
            msg += f"Market: {result.get('market', 'N/A')}\n"
            msg += f"Score: {result.get('score', 'N/A')}"
            QMessageBox.information(self, "Parser Test", msg)
        else:
            QMessageBox.warning(self, "Parser Test", "❌ Failed to parse test message")
    
    def get_settings(self):
        """Get Telegram settings"""
        return {
            "api_id": self.api_id_input.text(),
            "api_hash": self.api_hash_input.text(),
            "phone": self.phone_input.text(),
            "auto_learn": self.auto_learn_check.isChecked(),
            "min_examples": self.min_examples_spin.value()
        }
