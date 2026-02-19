import sqlite3
import os
import time
import logging
from core.config_paths import DATA_DIR

class Database:
    def __init__(self):
        self.logger = logging.getLogger("Database")
        os.makedirs(DATA_DIR, exist_ok=True)
        self.db_path = os.path.join(DATA_DIR, "dom2.db")
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            # Assicuriamoci che la colonna timestamp esista
            conn.execute("""
                CREATE TABLE IF NOT EXISTS journal (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tx_id TEXT UNIQUE,
                    amount REAL,
                    status TEXT,
                    payout REAL DEFAULT 0,
                    timestamp INTEGER
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS balance (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    current_balance REAL
                )
            """)
            # Saldo iniziale demo (modificabile) se vuoto
            conn.execute("INSERT OR IGNORE INTO balance (id, current_balance) VALUES (1, 100.0)")

    def get_balance(self):
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute("SELECT current_balance FROM balance WHERE id = 1")
            row = cur.fetchone()
            return float(row[0]) if row else 0.0

    def reserve(self, tx_id, amount):
        with sqlite3.connect(self.db_path) as conn:
            # 🔴 FIX: Inserimento Timestamp Reale per il Timeout Deadlock
            ts = int(time.time())
            conn.execute("INSERT INTO journal (tx_id, amount, status, timestamp) VALUES (?, ?, 'PENDING', ?)", (tx_id, amount, ts))
            conn.execute("UPDATE balance SET current_balance = current_balance - ? WHERE id = 1", (amount,))

    def commit(self, tx_id, payout):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("UPDATE journal SET status = 'SETTLED', payout = ? WHERE tx_id = ?", (payout, tx_id))
            if payout > 0:
                conn.execute("UPDATE balance SET current_balance = current_balance + ? WHERE id = 1", (payout,))

    def rollback(self, tx_id):
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute("SELECT amount FROM journal WHERE tx_id = ? AND status = 'PENDING'", (tx_id,))
            row = cur.fetchone()
            if row:
                amount = row[0]
                conn.execute("UPDATE journal SET status = 'VOID' WHERE tx_id = ?", (tx_id,))
                conn.execute("UPDATE balance SET current_balance = current_balance + ? WHERE id = 1", (amount,))

    def pending(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.execute("SELECT * FROM journal WHERE status = 'PENDING' ORDER BY timestamp ASC")
            return [dict(row) for row in cur.fetchall()]
