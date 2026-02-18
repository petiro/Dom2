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
    _lock = threading.Lock()

    def __new__(cls):
        if not cls._instance:
            with cls._lock:
                if not cls._instance:
                    cls._instance = super().__new__(cls)
                    cls._instance._init_db()
        return cls._instance

    def _init_db(self):
        os.makedirs(CONFIG_DIR, exist_ok=True)
        self.logger = logging.getLogger("DB")
        self.conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row

        # WAL Mode & Settings
        self.conn.execute("PRAGMA journal_mode=WAL;")
        self.conn.execute("PRAGMA synchronous=NORMAL;")
        self.conn.execute("PRAGMA busy_timeout=5000;") # Wait up to 5s

        self._create()

    def _execute_retry(self, func, *args):
        """Wrapper per gestire i lock di SQLite in modalità WAL."""
        for i in range(5):
            try:
                return func(*args)
            except sqlite3.OperationalError as e:
                if "locked" in str(e).lower():
                    time.sleep(0.1 + (i * 0.1)) # Backoff
                    continue
                raise
        raise sqlite3.OperationalError("Database locked after 5 retries")

    def _create(self):
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
            if s > bal: raise ValueError("Insufficient funds")

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
                raise e

    def commit(self, tx_id, payout=0):
        def _op():
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
            except:
                self.conn.rollback()

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
            except:
                self.conn.rollback()

    def pending(self):
        with self._lock:
            return self.conn.execute("SELECT * FROM journal WHERE status='PENDING'").fetchall()