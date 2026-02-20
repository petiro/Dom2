from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, 
                               QLabel, QLineEdit, QPushButton, QListWidget, QGroupBox)
from core.secure_storage import SelectorManager

class SelectorsTab(QWidget):
    def __init__(self):
        super().__init__()
        self.manager = SelectorManager()

        layout = QHBoxLayout(self)
        
        # --- PANNELLO SINISTRO (Lista) ---
        left_panel = QVBoxLayout()
        left_panel.addWidget(QLabel("🧩 SELETTORI DOM:"))
        
        self.list = QListWidget()
        left_panel.addWidget(self.list)

        btn_del = QPushButton("❌ Elimina Selezionato")
        btn_del.setStyleSheet("background-color: #c0392b; color: white; padding: 5px;")
        btn_del.clicked.connect(self.delete_selected)
        left_panel.addWidget(btn_del)
        
        # --- PANNELLO DESTRO (Form) ---
        right_group = QGroupBox("Aggiungi Nuovo Selettore")
        right_layout = QVBoxLayout()
        form = QFormLayout()

        self.name = QLineEdit()
        self.name.setPlaceholderText("Es: pulsante_quota")
        self.book = QLineEdit()
        self.book.setPlaceholderText("Es: Bet365")
        self.value = QLineEdit()
        self.value.setPlaceholderText("Es: .gl-Participant_Odds")

        form.addRow("Nome selettore:", self.name)
        form.addRow("Bookmaker target:", self.book)
        form.addRow("Valore (CSS/XPath):", self.value)
        
        right_layout.addLayout(form)

        btn_add = QPushButton("➕ Salva Selettore")
        btn_add.setStyleSheet("background-color: #2980b9; color: white; font-weight: bold; padding: 8px;")
        btn_add.clicked.connect(self.add_selector)
        right_layout.addWidget(btn_add)
        
        right_group.setLayout(right_layout)

        # Aggiungi al layout principale
        layout.addLayout(left_panel, 1)
        layout.addWidget(right_group, 2)
        
        self.refresh()

    def refresh(self):
        self.list.clear()
        for s in self.manager.all():
            self.list.addItem(f"{s['name']} | Book: {s['bookmaker']} | {s['value']}")

    def add_selector(self):
        if self.name.text() and self.value.text():
            self.manager.add(self.name.text(), self.book.text(), self.value.text())
            # Svuota i campi dopo aver salvato
            self.name.clear()
            self.book.clear()
            self.value.clear()
            self.refresh()

    def delete_selected(self):
        row = self.list.currentRow()
        if row < 0: return
        data = self.manager.all()
        self.manager.delete(data[row]["id"])
        self.refresh()
