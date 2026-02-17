import sys
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                               QTabWidget, QScrollArea, QLabel)
from core.logger import setup_logger
from core.controller import SuperAgentController

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SuperAgent Dom2 V7.4")
        self.setMinimumSize(900, 700)
        
        self.logger = setup_logger()
        self.controller = SuperAgentController(self.logger)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        main_widget = QWidget()
        self.layout = QVBoxLayout(main_widget)
        scroll.setWidget(main_widget)
        self.setCentralWidget(scroll)
        
        self.tabs = QTabWidget()
        self.layout.addWidget(self.tabs)
        
        self.create_dashboard()
        self.controller.start_system()

    def create_dashboard(self):
        t = QWidget()
        self.tabs.addTab(t, "Dashboard")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec())