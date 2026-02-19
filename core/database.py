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
        
        # Connessione persistente e thread-safe
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self):
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
        self.conn.execute("INSERT OR IGNORE INTO balance (id, current_balance) VALUES (1, 100.0)")
        self.conn.commit()

    def get_balance(self):
        cur = self.conn.execute("SELECT current_balance FROM balance WHERE id = 1")
        row = cur.fetchone()
        return float(row["current_balance"]) if row else 0.0

    def reserve(self, tx_id, amount):
        ts = int(time.time())
        
        # 🔴 FIX CRITICO: SQLite non accetta Decimal. Cast a float per la persistenza.
        amount = float(amount)
        
        self.conn.execute(
            "INSERT INTO journal (tx_id, amount, status, timestamp) VALUES (?, ?, 'PENDING', ?)", 
            (tx_id, amount, ts)
        )
        self.conn.execute(
            "UPDATE balance SET current_balance = current_balance - ? WHERE id = 1", 
            (amount,)
        )
        self.conn.commit()

    def commit(self, tx_id, payout):
        # 🔴 FIX CRITICO: Cast a float
        payout = float(payout)
        
        self.conn.execute(
            "UPDATE journal SET status = 'SETTLED', payout = ? WHERE tx_id = ?", 
            (payout, tx_id)
        )
        if payout > 0:
            self.conn.execute(
                "UPDATE balance SET current_balance = current_balance + ? WHERE id = 1", 
                (payout,)
            )
        self.conn.commit()

    def rollback(self, tx_id):
        cur = self.conn.execute("SELECT amount FROM journal WHERE tx_id = ? AND status = 'PENDING'", (tx_id,))
        row = cur.fetchone()
        if row:
            # 🔴 FIX CRITICO: Cast a float per sicurezza totale
            amount = float(row["amount"])
            
            self.conn.execute(
                "UPDATE journal SET status = 'VOID' WHERE tx_id = ?", 
                (tx_id,)
            )
            self.conn.execute(
                "UPDATE balance SET current_balance = current_balance + ? WHERE id = 1", 
                (amount,)
            )
            self.conn.commit()

    def pending(self):
        cur = self.conn.execute("SELECT * FROM journal WHERE status = 'PENDING' ORDER BY timestamp ASC")
        return [dict(row) for row in cur.fetchall()]
