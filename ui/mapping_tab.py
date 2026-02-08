from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton, QTextEdit, QLabel

class MappingTab(QWidget):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller

        layout = QVBoxLayout()
        layout.addWidget(QLabel("🔗 Inserisci il link del sito da mappare:"))

        nav_layout = QHBoxLayout()
        self.url_input = QLineEdit()
        self.btn_map = QPushButton("🚀 Genera Mappatura AI")
        self.btn_map.clicked.connect(self.start_mapping)
        nav_layout.addWidget(self.url_input)
        nav_layout.addWidget(self.btn_map)
        layout.addLayout(nav_layout)

        layout.addWidget(QLabel("📝 YAML Generato:"))
        self.yaml_display = QTextEdit()
        layout.addWidget(self.yaml_display)

        self.btn_test = QPushButton("👁️ Testa Mappatura sul Browser")
        self.btn_test.clicked.connect(self.test_mapping)
        layout.addWidget(self.btn_test)

        self.btn_save = QPushButton("💾 Salva in selectors.yaml")
        self.btn_save.clicked.connect(self.save_mapping)
        layout.addWidget(self.btn_save)

        self.setLayout(layout)
        
        # Connessione segnale dal controller
        self.controller.mapping_ready.connect(self.yaml_display.setText)

    def start_mapping(self):
        url = self.url_input.text().strip()
        if url:
            self.yaml_display.setText("⏳ Analisi del sito...")
            self.controller.request_auto_mapping(url)

    def test_mapping(self):
        yaml_code = self.yaml_display.toPlainText()
        if yaml_code:
            self.controller.test_mapping_visual(yaml_code)

    def save_mapping(self):
        yaml_code = self.yaml_display.toPlainText()
        if yaml_code:
            self.controller.save_selectors_yaml(yaml_code)
