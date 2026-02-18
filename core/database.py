import sqlite3
import logging
import threading
import time
from decimal import Decimal
import os
from core.config_paths import CONFIG_DIR

DB_PATH = os.path.join(CONFIG_DIR, "dom2_cluster.db")

class Database:
    _instance = None
    _instance_lock = threading.Lock()

    def __new__(cls):
        if not cls._instance:
            with cls._instance_lock:
                if not cls._instance:
                    cls._instance = super().__new__(cls)
                    cls._instance._init_db()
        return cls._instance

    def _init_db(self):
        os.makedirs(CONFIG_DIR, exist_ok=True)
        self.logger = logging.getLogger("Database")
        
        self._lock = threading.RLock()

        self.conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row

        # WAL Mode & Settings
        self.conn.execute("PRAGMA journal_mode=WAL;")
        self.conn.execute("PRAGMA synchronous=NORMAL;")
        self.conn.execute("PRAGMA busy_timeout=5000;")

        self._create_tables()

    def _execute_retry(self, func):
        for i in range(6):
            try:
                return func()
            except sqlite3.OperationalError as e:
                if "locked" in str(e).lower():
                    time.sleep(0.15 * (i + 1))
                    continue
                raise
        raise sqlite3.OperationalError("Database locked after 6 retries")

    def _create_tables(self):
        with self._lock:
            self.conn.execute("""
            CREATE TABLE IF NOT EXISTS bankroll(
                id INTEGER PRIMARY KEY,
                amount TEXT,
                updated REAL
            )""")

            self.conn.execute("""
            CREATE TABLE IF NOT EXISTS journal(
                tx_id TEXT PRIMARY KEY,
                status TEXT,
                stake TEXT,
                odds TEXT,
                created REAL,
                completed REAL
            )""")

            res = self.conn.execute("SELECT count(*) FROM bankroll").fetchone()[0]
            if res == 0:
                self.conn.execute("INSERT INTO bankroll VALUES(1,'100.00',?)",(time.time(),))
                self.conn.commit()

    def get_balance(self):
        with self._lock:
            row = self.conn.execute("SELECT amount FROM bankroll WHERE id=1").fetchone()
            return Decimal(row[0])

    def reserve(self, tx_id, stake):
        def _op():
            bal = self.get_balance()
            s = Decimal(str(stake))
            
            if s <= 0: raise ValueError("Invalid stake")
            if s > bal: raise ValueError("Insufficient funds")

            exists = self.conn.execute("SELECT tx_id FROM journal WHERE tx_id=?", (tx_id,)).fetchone()
            if exists: raise ValueError("TX already exists")

            self.conn.execute("INSERT INTO journal VALUES(?,?,?,?,?,?)",
                              (tx_id,"PENDING",str(stake),"0",time.time(),0))
            
            new = bal - s
            self.conn.execute("UPDATE bankroll SET amount=?,updated=? WHERE id=1",
                              (str(new),time.time()))
            self.conn.commit()

        with self._lock:
            try:
                self._execute_retry(_op)
            except Exception as e:
                self.conn.rollback()
                self.logger.error(f"Reserve failed: {e}")
                raise

    def commit(self, tx_id, payout=0):
        def _op():
            row = self.conn.execute("SELECT status FROM journal WHERE tx_id=?", (tx_id,)).fetchone()
            if not row or row["status"] != "PENDING": return

            if payout > 0:
                bal = self.get_balance()
                new = bal + Decimal(str(payout))
                self.conn.execute("UPDATE bankroll SET amount=?,updated=? WHERE id=1",
                                  (str(new),time.time()))

            self.conn.execute("UPDATE journal SET status='DONE',completed=? WHERE tx_id=?",
                              (time.time(),tx_id))
            self.conn.commit()

        with self._lock:
            try:
                self._execute_retry(_op)
            except Exception as e:
                self.conn.rollback()
                self.logger.error(f"Commit error {tx_id}: {e}")

    def rollback(self, tx_id):
        def _op():
            row = self.conn.execute("SELECT stake,status FROM journal WHERE tx_id=?",(tx_id,)).fetchone()
            if row and row["status"]=="PENDING":
                stake = Decimal(row["stake"])
                bal = self.get_balance()
                self.conn.execute("UPDATE bankroll SET amount=?,updated=? WHERE id=1",
                                  (str(bal+stake),time.time()))
                self.conn.execute("UPDATE journal SET status='ROLLBACK',completed=? WHERE tx_id=?",
                                  (time.time(),tx_id))
                self.conn.commit()

        with self._lock:
            try:
                self._execute_retry(_op)
            except Exception as e:
                self.conn.rollback()
                self.logger.error(f"Rollback error {tx_id}: {e}")

    def pending(self):
        with self._lock:
            return self.conn.execute("SELECT * FROM journal WHERE status='PENDING'").fetchall()