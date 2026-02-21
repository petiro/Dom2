import os
import json
import shutil
import threading
import time
import sqlite3
from datetime import datetime
from pathlib import Path
from core.crypto_vault import CryptoVault

BASE_DIR = os.path.join(str(Path.home()), ".superagent_data")
os.makedirs(BASE_DIR, exist_ok=True)

BOOKMAKER_FILE = os.path.join(BASE_DIR, "bookmakers.json")
ROBOTS_FILE = os.path.join(BASE_DIR, "robots.json")
SELECTORS_FILE = os.path.join(BASE_DIR, "selectors.json")
BACKUP_DIR = os.path.join(BASE_DIR, "backups")

os.makedirs(BACKUP_DIR, exist_ok=True)

# 🔴 FIX NUCLEARE I/O: Lucchetto Globale per la lettura/scrittura dei file JSON
_io_lock = threading.RLock()

def _load(path, default):
    with _io_lock:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f: return json.load(f)
            except Exception: return default
        return default

def _save(path, data):
    with _io_lock:
        with open(path, "w", encoding="utf-8") as f: json.dump(data, f, indent=4)

# ================================
# AUTO-BACKUP ATOMICO (Hedge-Grade)
# ================================
class BackupEngine:
    @staticmethod
    def start_auto_backup(interval_minutes=30):
        def _loop():
            while True:
                time.sleep(interval_minutes * 60)
                BackupEngine.create_snapshot()
        t = threading.Thread(target=_loop, daemon=True)
        t.start()

    @staticmethod
    def create_snapshot():
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            temp_dir = os.path.join(BACKUP_DIR, f"temp_{timestamp}")
            os.makedirs(temp_dir, exist_ok=True)
            
            files_to_backup = ["bookmakers.json", "robots.json", "selectors.json", "telegram_session.dat", "openrouter_key.dat", ".master.key"]
            for file in files_to_backup:
                src = os.path.join(BASE_DIR, file)
                if os.path.exists(src): shutil.copy2(src, temp_dir)
            
            db_src = os.path.join(BASE_DIR, "money_db.sqlite")
            db_dst = os.path.join(temp_dir, "money_db.sqlite")
            if os.path.exists(db_src):
                with sqlite3.connect(db_src) as conn_src, sqlite3.connect(db_dst) as conn_dst:
                    conn_src.backup(conn_dst)
                    
            zip_name = os.path.join(BACKUP_DIR, f"superagent_backup_{timestamp}")
            shutil.make_archive(zip_name, 'zip', temp_dir)
            shutil.rmtree(temp_dir)
            
            backups = sorted([f for f in os.listdir(BACKUP_DIR) if f.endswith(".zip")])
            if len(backups) > 48: os.remove(os.path.join(BACKUP_DIR, backups[0]))
        except Exception: pass

BackupEngine.start_auto_backup()

# ================================
# MANAGER CRIPTATI E SICURI
# ================================
class BookmakerManager:
    def all(self): return _load(BOOKMAKER_FILE, [])
    def save_all(self, data): _save(BOOKMAKER_FILE, data)
    def add(self, name, username, password):
        data = self.all()
        enc_pass = CryptoVault.encrypt(password)
        data.append({"id": name.lower().replace(" ", "_"), "name": name, "username": username, "password": enc_pass})
        self.save_all(data)
    def delete(self, book_id): self.save_all([b for b in self.all() if b["id"] != book_id])
    def get_decrypted(self, book_id):
        for b in self.all():
            if b["id"] == book_id:
                return b["username"], CryptoVault.decrypt(b["password"])
        return "", ""

class RobotManager:
    def all(self): return _load(ROBOTS_FILE, [])
    def save_all(self, data): _save(ROBOTS_FILE, data)
    def add(self, name, book_id):
        data = self.all(); data.append({"id": name.lower().replace(" ", "_"), "name": name, "bookmaker_id": book_id, "selectors": []})
        self.save_all(data)
        
    # 🔴 FIX: Aggiunta funzione 'save' usata dal tester per la sovrascrittura sicura
    def save(self, robot_id, bot_data):
        data = self.all()
        found = False
        for r in data:
            if r.get("id") == robot_id:
                r.update(bot_data)
                found = True
                break
        if not found:
            bot_data["id"] = robot_id
            data.append(bot_data)
        self.save_all(data)
        
    def delete(self, robot_id): self.save_all([r for r in self.all() if r["id"] != robot_id])

class SelectorManager:
    def all(self): return _load(SELECTORS_FILE, [])
    def save_all(self, data): _save(SELECTORS_FILE, data)
    def add(self, name, book, val):
        data = self.all(); data.append({"id": name.lower().replace(" ", "_"), "name": name, "bookmaker": book, "value": val})
        self.save_all(data)
    def delete(self, sel_id): self.save_all([s for s in self.all() if s["id"] != sel_id])