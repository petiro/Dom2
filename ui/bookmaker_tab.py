from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, 
                               QLabel, QLineEdit, QPushButton, QListWidget, QGroupBox)
from core.secure_storage import BookmakerManager

class BookmakerTab(QWidget):
    def __init__(self):
        super().__init__()
        self.manager = BookmakerManager()

        layout = QHBoxLayout(self)
        
        # --- PANNELLO SINISTRO (Lista) ---
        left_panel = QVBoxLayout()
        left_panel.addWidget(QLabel("🏦 ACCOUNT BOOKMAKERS:"))
        
        self.list = QListWidget()
        left_panel.addWidget(self.list)

        btn_del = QPushButton("❌ Elimina Selezionato")
        btn_del.setStyleSheet("background-color: #c0392b; color: white; padding: 5px;")
        btn_del.clicked.connect(self.delete_selected)
        left_panel.addWidget(btn_del)
        
        # --- PANNELLO DESTRO (Form) ---
        right_group = QGroupBox("Aggiungi Nuovo Account")
        right_layout = QVBoxLayout()
        form = QFormLayout()

        self.name = QLineEdit()
        self.name.setPlaceholderText("Es: Bet365_Principale")
        self.user = QLineEdit()
        self.pwd = QLineEdit()
        self.pwd.setEchoMode(QLineEdit.Password)

        form.addRow("Nome Bookmaker:", self.name)
        form.addRow("Username:", self.user)
        form.addRow("Password:", self.pwd)
        
        right_layout.addLayout(form)

        btn_add = QPushButton("➕ Salva Bookmaker")
        btn_add.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold; padding: 8px;")
        btn_add.clicked.connect(self.add_bookmaker)
        right_layout.addWidget(btn_add)
        
        right_group.setLayout(right_layout)

        # Aggiungi al layout principale
        layout.addLayout(left_panel, 1)
        layout.addWidget(right_group, 2)
        
        self.refresh()

    def refresh(self):
        self.list.clear()
        for b in self.manager.all():
            # Mostra solo il nome e l'username, la password (cifrata) resta invisibile
            self.list.addItem(f"{b['name']} | User: {b['username']}")

    def add_bookmaker(self):
        if self.name.text() and self.user.text() and self.pwd.text():
            self.manager.add(self.name.text(), self.user.text(), self.pwd.text())
            # Svuota i campi dopo il salvataggio
            self.name.clear()
            self.user.clear()
            self.pwd.clear()
            self.refresh()

    def delete_selected(self):
        row = self.list.currentRow()
        if row < 0: return
        data = self.manager.all()
        self.manager.delete(data[row]["id"])
        self.refresh()
