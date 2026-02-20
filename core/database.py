import sqlite3
import os
import time
import logging
import threading
from pathlib import Path

# 🔴 Database Finanziario nel Vault immortale
DB_DIR = os.path.join(str(Path.home()), ".superagent_data")
os.makedirs(DB_DIR, exist_ok=True)
DB_FILE = "money_db.sqlite"
DB_PATH = os.path.join(DB_DIR, DB_FILE)

class Database:
    def __init__(self):
        self.logger = logging.getLogger("Database")
        
        # 🔴 FIX HEDGE-GRADE: Threading sicuro + Timeout anti-lock
        self.conn = sqlite3.connect(
            DB_PATH, 
            check_same_thread=False,
            timeout=30,
            isolation_level=None
        )
        self.conn.row_factory = sqlite3.Row
        
        # 🔴 FIX HEDGE-GRADE: PRAGMA WAL per scritture concorrenti UI/Worker
        self.conn.execute("PRAGMA journal_mode=WAL;")
        self.conn.execute("PRAGMA synchronous=NORMAL;")
        
        self._lock = threading.RLock()
        self._init_db()

    def _init_db(self):
        with self._lock:
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS journal (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tx_id TEXT UNIQUE,
                    amount REAL,
                    status TEXT,
                    payout REAL DEFAULT 0,
                    timestamp INTEGER
                )
            """)
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS balance (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    current_balance REAL
                )
            """)
            # Inizializza saldo a 1000 se vuoto (adattalo se vuoi un altro default)
            self.conn.execute("INSERT OR IGNORE INTO balance (id, current_balance) VALUES (1, 1000.0)")

    def get_balance(self):
        with self._lock:
            cur = self.conn.execute("SELECT current_balance FROM balance WHERE id = 1")
            row = cur.fetchone()
            return float(row["current_balance"]) if row else 0.0

    def reserve(self, tx_id, amount):
        ts = int(time.time())
        amount = float(amount)
        with self._lock:
            self.conn.execute("BEGIN TRANSACTION")
            try:
                self.conn.execute("INSERT INTO journal (tx_id, amount, status, timestamp) VALUES (?, ?, 'PENDING', ?)", (tx_id, amount, ts))
                self.conn.execute("UPDATE balance SET current_balance = current_balance - ? WHERE id = 1", (amount,))
                self.conn.execute("COMMIT")
            except Exception:
                self.conn.execute("ROLLBACK")
                raise

    def commit(self, tx_id, payout):
        payout = float(payout)
        with self._lock:
            self.conn.execute("BEGIN TRANSACTION")
            try:
                self.conn.execute("UPDATE journal SET status = 'SETTLED', payout = ? WHERE tx_id = ?", (payout, tx_id))
                if payout > 0:
                    self.conn.execute("UPDATE balance SET current_balance = current_balance + ? WHERE id = 1", (payout,))
                self.conn.execute("COMMIT")
            except Exception:
                self.conn.execute("ROLLBACK")
                raise

    def rollback(self, tx_id):
        with self._lock:
            self.conn.execute("BEGIN TRANSACTION")
            try:
                cur = self.conn.execute("SELECT amount FROM journal WHERE tx_id = ? AND status = 'PENDING'", (tx_id,))
                row = cur.fetchone()
                if row:
                    amount = float(row["amount"])
                    self.conn.execute("UPDATE journal SET status = 'VOID' WHERE tx_id = ?", (tx_id,))
                    self.conn.execute("UPDATE balance SET current_balance = current_balance + ? WHERE id = 1", (amount,))
                self.conn.execute("COMMIT")
            except Exception:
                self.conn.execute("ROLLBACK")
                raise

    def pending(self):
        with self._lock:
            cur = self.conn.execute("SELECT * FROM journal WHERE status = 'PENDING' ORDER BY timestamp ASC")
            return [dict(row) for row in cur.fetchall()]

    def close(self) -> None:
        try:
            if self.conn:
                self.conn.close()
        except Exception:
            pass