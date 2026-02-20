from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, 
                               QLabel, QLineEdit, QPushButton, QListWidget, QGroupBox, QComboBox, QMessageBox)
from core.secure_storage import RobotManager, BookmakerManager

class RobotsTab(QWidget):
    def __init__(self, logger, controller):
        super().__init__()
        self.logger = logger
        self.controller = controller
        self.manager = RobotManager()
        self.current_idx = -1
        
        layout = QHBoxLayout(self)
        
        # --- PANNELLO SINISTRO ---
        left_panel = QVBoxLayout()
        left_panel.addWidget(QLabel("🤖 ROBOTS ATTIVI:"))
        
        self.list = QListWidget()
        self.list.currentRowChanged.connect(self.select_item)
        left_panel.addWidget(self.list)

        btn_del = QPushButton("❌ Elimina Robot")
        btn_del.setStyleSheet("background-color: #c0392b; color: white;")
        btn_del.clicked.connect(self.delete_selected)
        left_panel.addWidget(btn_del)
        
        # --- PANNELLO DESTRO ---
        right_group = QGroupBox("Configurazione Strategia")
        right_layout = QVBoxLayout()
        form = QFormLayout()

        self.in_name = QLineEdit(); self.in_name.textChanged.connect(self.update_data)
        
        # 🔴 Dropdown dinamico con gli account Bookmaker salvati
        self.in_book = QComboBox()
        self.in_book.addItems([b.get("id") for b in BookmakerManager().all()])
        self.in_book.currentTextChanged.connect(self.update_data)
        
        self.in_triggers = QLineEdit(); self.in_triggers.textChanged.connect(self.update_data)
        self.in_stake = QLineEdit(); self.in_stake.textChanged.connect(self.update_data)

        form.addRow("Nome Robot:", self.in_name)
        form.addRow("Collega a Account:", self.in_book)
        form.addRow("Trigger Words (es. OVER):", self.in_triggers)
        form.addRow("Stake Fisso (€):", self.in_stake)
        
        right_layout.addLayout(form)

        btn_add = QPushButton("➕ Crea Nuovo Robot")
        btn_add.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold; padding: 8px;")
        btn_add.clicked.connect(self.add_robot)
        right_layout.addWidget(btn_add)
        
        right_group.setLayout(right_layout)

        layout.addLayout(left_panel, 1)
        layout.addWidget(right_group, 2)
        
        self.refresh()

    def refresh(self):
        self.list.clear()
        self.in_book.clear()
        self.in_book.addItems([b.get("id") for b in BookmakerManager().all()])
        for r in self.manager.all():
            self.list.addItem(f"{r['name']} ➔ {r.get('bookmaker_id', 'Nessuno')}")

    def select_item(self, idx):
        if idx < 0: return
        self.current_idx = idx
        d = self.manager.all()[idx]
        
        self.in_name.blockSignals(True); self.in_book.blockSignals(True); self.in_triggers.blockSignals(True); self.in_stake.blockSignals(True)
        self.in_name.setText(d.get("name", ""))
        self.in_book.setCurrentText(d.get("bookmaker_id", ""))
        self.in_triggers.setText(", ".join(d.get("trigger_words", [])))
        self.in_stake.setText(str(d.get("stake", "2.0")))
        self.in_name.blockSignals(False); self.in_book.blockSignals(False); self.in_triggers.blockSignals(False); self.in_stake.blockSignals(False)

    def update_data(self):
        if self.current_idx < 0: return
        data = self.manager.all()
        d = data[self.current_idx]
        d["name"] = self.in_name.text()
        d["bookmaker_id"] = self.in_book.currentText()
        d["trigger_words"] = [w.strip() for w in self.in_triggers.text().split(",") if w.strip()]
        d["stake"] = self.in_stake.text()
        self.manager.save_all(data)
        self.list.item(self.current_idx).setText(f"{d['name']} ➔ {d['bookmaker_id']}")

    def add_robot(self):
        self.manager.add("Nuovo Robot", "")
        self.refresh()
        self.list.setCurrentRow(len(self.manager.all())-1)

    def delete_selected(self):
        row = self.list.currentRow()
        if row < 0: return
        data = self.manager.all()
        self.manager.delete(data[row]["id"])
        self.refresh()
