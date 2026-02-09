from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton, QTextEdit, QLabel

class MappingTab(QWidget):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        
        layout = QVBoxLayout()
        
        # Input
        h_layout = QHBoxLayout()
        self.url_in = QLineEdit()
        self.url_in.setPlaceholderText("https://sito...")
        btn_map = QPushButton("🤖 Mappa con AI")
        btn_map.clicked.connect(self.start_map)
        h_layout.addWidget(self.url_in)
        h_layout.addWidget(btn_map)
        layout.addLayout(h_layout)
        
        # Output
        self.yaml_out = QTextEdit()
        layout.addWidget(self.yaml_out)
        
        # Actions
        btn_test = QPushButton("👁️ Highlight (Test)")
        btn_test.clicked.connect(self.do_test)
        btn_save = QPushButton("💾 Salva Selectors")
        btn_save.clicked.connect(self.do_save)
        
        layout.addWidget(btn_test)
        layout.addWidget(btn_save)
        self.setLayout(layout)
        
        # Signals
        self.controller.mapping_ready.connect(self.yaml_out.setText)

    def start_map(self):
        self.yaml_out.setText("⏳ Analisi in corso...")
        self.controller.request_auto_mapping(self.url_in.text())

    def do_test(self):
        self.controller.test_mapping_visual(self.yaml_out.toPlainText())

    def do_save(self):
        self.controller.save_selectors_yaml(self.yaml_out.toPlainText())
