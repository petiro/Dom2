"""
SuperAgent Desktop UI - Modern Interface
Combines AI learning, RPA automation, and desktop interface
"""
import sys
import json
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
        
        # Title
        title = QLabel("🤖 AI Assistant")
        title.setFont(QFont("Arial", 16, QFont.Bold))
        layout.addWidget(title)
        
        # Chat history
        self.chat_history = QTextEdit()
        self.chat_history.setReadOnly(True)
        self.chat_history.setPlaceholderText("AI responses will appear here...")
        layout.addWidget(self.chat_history)
        
        # Input area
        input_group = QGroupBox("Your Message")
        input_layout = QVBoxLayout(input_group)
        
        self.input_text = QTextEdit()
        self.input_text.setPlaceholderText("Type your message here...")
        self.input_text.setMaximumHeight(100)
        input_layout.addWidget(self.input_text)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        self.send_btn = QPushButton("📤 Send")
        self.send_btn.clicked.connect(self.send_message)
        self.send_btn.setStyleSheet("background-color: #4CAF50; color: white; padding: 10px; font-weight: bold;")
        
        self.clear_btn = QPushButton("🗑️ Clear")
        self.clear_btn.clicked.connect(self.clear_chat)
        
        btn_layout.addWidget(self.send_btn)
        btn_layout.addWidget(self.clear_btn)
        btn_layout.addStretch()
        
        input_layout.addLayout(btn_layout)
        layout.addWidget(input_group)
        
        # Progress bar
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        self.progress.setRange(0, 0)  # Indeterminate
        layout.addWidget(self.progress)
    
    def send_message(self):
        if not self.vision:
            QMessageBox.warning(self, "Error", "AI not initialized. Check API key in settings.")
            return
        
        prompt = self.input_text.toPlainText().strip()
        if not prompt:
            return
        
        # Add user message to history
        self.append_message("You", prompt, "#2196F3")
        
        # Disable button and show progress
        self.send_btn.setEnabled(False)
        self.progress.setVisible(True)
        
        # Start worker thread
        self.worker = AIWorker(self.vision, prompt)
        self.worker.finished.connect(self.on_response)
        self.worker.error.connect(self.on_error)
        self.worker.start()
        
        # Clear input
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


class RPAMonitorTab(QWidget):
    """RPA monitoring and control tab"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # Title
        title = QLabel("🔧 RPA Monitor")
        title.setFont(QFont("Arial", 16, QFont.Bold))
        layout.addWidget(title)
        
        # Status panel
        status_group = QGroupBox("Agent Status")
        status_layout = QVBoxLayout(status_group)
        
        self.status_label = QLabel("Status: <b style='color: gray;'>IDLE</b>")
        self.uptime_label = QLabel("Uptime: 0 seconds")
        self.tasks_label = QLabel("Tasks completed: 0")
        
        status_layout.addWidget(self.status_label)
        status_layout.addWidget(self.uptime_label)
        status_layout.addWidget(self.tasks_label)
        
        layout.addWidget(status_group)
        
        # Selector healing panel
        healing_group = QGroupBox("Selector Healing")
        healing_layout = QVBoxLayout(healing_group)
        
        self.healing_table = QTableWidget()
        self.healing_table.setColumnCount(4)
        self.healing_table.setHorizontalHeaderLabels(["Timestamp", "Selector", "Old", "New"])
        self.healing_table.horizontalHeader().setStretchLastSection(True)
        
        healing_layout.addWidget(self.healing_table)
        
        layout.addWidget(healing_group)
        
        # Control buttons
        control_layout = QHBoxLayout()
        
        self.start_btn = QPushButton("▶️ Start Agent")
        self.start_btn.setStyleSheet("background-color: #4CAF50; color: white; padding: 10px;")
        
        self.stop_btn = QPushButton("⏸️ Stop Agent")
        self.stop_btn.setEnabled(False)
        self.stop_btn.setStyleSheet("background-color: #f44336; color: white; padding: 10px;")
        
        self.test_healing_btn = QPushButton("🔧 Test Healing")
        
        control_layout.addWidget(self.start_btn)
        control_layout.addWidget(self.stop_btn)
        control_layout.addWidget(self.test_healing_btn)
        control_layout.addStretch()
        
        layout.addLayout(control_layout)
    
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
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # Title
        title = QLabel("📊 Learning Statistics")
        title.setFont(QFont("Arial", 16, QFont.Bold))
        layout.addWidget(title)
        
        # Telegram learning stats
        telegram_group = QGroupBox("Telegram Learning")
        telegram_layout = QVBoxLayout(telegram_group)
        
        self.telegram_messages = QLabel("Total messages: 0")
        self.telegram_patterns = QLabel("Learned patterns: 0")
        self.telegram_success = QLabel("Success rate: 0%")
        
        telegram_layout.addWidget(self.telegram_messages)
        telegram_layout.addWidget(self.telegram_patterns)
        telegram_layout.addWidget(self.telegram_success)
        
        layout.addWidget(telegram_group)
        
        # RPA healing stats
        rpa_group = QGroupBox("RPA Self-Healing")
        rpa_layout = QVBoxLayout(rpa_group)
        
        self.rpa_healings = QLabel("Total healings: 0")
        self.rpa_auto_updated = QLabel("Auto-updated: 0")
        self.rpa_success = QLabel("Success rate: 0%")
        
        rpa_layout.addWidget(self.rpa_healings)
        rpa_layout.addWidget(self.rpa_auto_updated)
        rpa_layout.addWidget(self.rpa_success)
        
        layout.addWidget(rpa_group)
        
        # Refresh button
        refresh_btn = QPushButton("🔄 Refresh Stats")
        refresh_btn.clicked.connect(self.refresh_stats)
        layout.addWidget(refresh_btn)
        
        layout.addStretch()
    
    def refresh_stats(self):
        # This will be connected to actual stats from the agent
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
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # Title
        title = QLabel("⚙️ Settings")
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
        
        self.autobet_check = QCheckBox("Enable Auto-Bet (⚠️ USE WITH CAUTION)")
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
        save_btn = QPushButton("💾 Save Settings")
        save_btn.setStyleSheet("background-color: #2196F3; color: white; padding: 10px; font-weight: bold;")
        save_btn.clicked.connect(self.save_settings)
        layout.addWidget(save_btn)
        
        layout.addStretch()
    
    def save_settings(self):
        QMessageBox.information(self, "Settings", "Settings saved successfully!")
    
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
        
        # Update timer
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_status)
        self.timer.start(1000)  # Update every second
        
        self.start_time = datetime.now()
    
    def init_ui(self):
        self.setWindowTitle("SuperAgent - Intelligent RPA Desktop")
        self.setGeometry(100, 100, 1200, 800)
        
        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        
        layout = QVBoxLayout(central)
        
        # Header
        header = QLabel("🤖 SuperAgent - Intelligent RPA System")
        header.setFont(QFont("Arial", 20, QFont.Bold))
        header.setAlignment(Qt.AlignCenter)
        header.setStyleSheet("background-color: #2196F3; color: white; padding: 15px; border-radius: 5px;")
        layout.addWidget(header)
        
        # Tab widget
        self.tabs = QTabWidget()
        
        # Create tabs
        self.chat_tab = ChatTab(self.vision)
        self.rpa_tab = RPAMonitorTab()
        self.telegram_tab = TelegramTab(self.agent, self.telegram_learner, self.logger)
        self.stats_tab = StatsTab()
        self.settings_tab = SettingsTab()
        
        self.tabs.addTab(self.chat_tab, "💬 AI Chat")
        self.tabs.addTab(self.rpa_tab, "🔧 RPA Monitor")
        self.tabs.addTab(self.telegram_tab, "📱 Telegram")
        self.tabs.addTab(self.stats_tab, "📊 Statistics")
        self.tabs.addTab(self.settings_tab, "⚙️ Settings")
        
        layout.addWidget(self.tabs)
        
        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")
        
        # Apply dark theme
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
