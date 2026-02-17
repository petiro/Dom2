import sqlite3
import logging
import threading
import time
from decimal import Decimal
from core.config_paths import CONFIG_DIR
import os

DB_PATH = os.path.join(CONFIG_DIR, "dom2_cluster.db")

class Database:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(Database, cls).__new__(cls)
                    cls._instance._init_db()
        return cls._instance

    def _init_db(self):
        self.logger = logging.getLogger("Database")
        os.makedirs(CONFIG_DIR, exist_ok=True)
        self.conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        
        # WAL Mode per Concorrenza 10/10
        self.conn.execute("PRAGMA journal_mode=WAL;")
        self.conn.execute("PRAGMA synchronous=NORMAL;")
        
        self._create_tables()

    def _create_tables(self):
        with self._lock:
            # Tabella Bankroll
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS bankroll (
                    id INTEGER PRIMARY KEY,
                    amount TEXT NOT NULL,
                    updated_at REAL
                )
            """)
            # Inizializza se vuoto
            res = self.conn.execute("SELECT count(*) FROM bankroll").fetchone()[0]
            if res == 0:
                self.conn.execute("INSERT INTO bankroll (id, amount, updated_at) VALUES (1, '100.00', ?)", (time.time(),))
                self.conn.commit()

            # Tabella Journal (Transazioni in volo) per Resilienza
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS journal (
                    tx_id TEXT PRIMARY KEY,
                    status TEXT, -- PENDING, COMMITTED, ROLLEDBACK
                    teams TEXT,
                    market TEXT,
                    stake TEXT,
                    odds TEXT,
                    created_at REAL,
                    completed_at REAL
                )
            """)
            self.conn.commit()

    def get_balance(self):
        with self._lock:
            cur = self.conn.execute("SELECT amount FROM bankroll WHERE id=1")
            return Decimal(cur.fetchone()[0])

    def reserve_funds(self, tx_id, amount, details):
        """Tenta di prenotare fondi. Transazione atomica."""
        with self._lock:
            try:
                # 1. Check saldo
                current = self.get_balance()
                dec_amount = Decimal(str(amount))
                
                if dec_amount > current:
                    raise ValueError("Insufficient funds")
                
                # 2. Scrivi Intent nel Journal (Stato PENDING)
                self.conn.execute("""
                    INSERT INTO journal (tx_id, status, teams, market, stake, created_at)
                    VALUES (?, 'PENDING', ?, ?, ?, ?)
                """, (tx_id, details.get('teams'), details.get('market'), str(amount), time.time()))

                # 3. Deduci provvisoriamente
                new_bal = current - dec_amount
                self.conn.execute("UPDATE bankroll SET amount=?, updated_at=? WHERE id=1", (str(new_bal), time.time()))
                
                self.conn.commit()
                return True
            except Exception as e:
                self.conn.rollback()
                self.logger.error(f"Transaction failed: {e}")
                raise e

    def commit_transaction(self, tx_id, profit=0):
        """Conferma il successo e accredita vincita eventuale."""
        with self._lock:
            try:
                # Se profit > 0, riaccredita stake + profitto
                if profit > 0:
                    cur = self.conn.execute("SELECT stake FROM journal WHERE tx_id=?", (tx_id,))
                    row = cur.fetchone()
                    if row:
                        original_stake = Decimal(row[0])
                        # Accredita: Stake (che era stato tolto) + Profitto netto (o Stake*Quota)
                        # Nota: Qui assumiamo profit sia il ritorno totale (Stake * Quota)
                        current = self.get_balance()
                        new_bal = current + Decimal(str(profit))
                        self.conn.execute("UPDATE bankroll SET amount=?, updated_at=? WHERE id=1", (str(new_bal), time.time()))

                self.conn.execute("UPDATE journal SET status='COMMITTED', completed_at=? WHERE tx_id=?", (time.time(), tx_id))
                self.conn.commit()
            except Exception as e:
                self.logger.error(f"Commit error: {e}")
                self.conn.rollback()

    def rollback_transaction(self, tx_id):
        """Annulla la transazione e rimborsa lo stake."""
        with self._lock:
            try:
                cur = self.conn.execute("SELECT stake, status FROM journal WHERE tx_id=?", (tx_id,))
                row = cur.fetchone()
                if row and row[1] == 'PENDING':
                    stake = Decimal(row[0])
                    current = self.get_balance()
                    new_bal = current + stake
                    self.conn.execute("UPDATE bankroll SET amount=?, updated_at=? WHERE id=1", (str(new_bal), time.time()))
                    self.conn.execute("UPDATE journal SET status='ROLLEDBACK', completed_at=? WHERE tx_id=?", (time.time(), tx_id))
                    self.conn.commit()
            except Exception as e:
                self.logger.error(f"Rollback error: {e}")
                self.conn.rollback()

    def get_pending_transactions(self):
        with self._lock:
            cur = self.conn.execute("SELECT * FROM journal WHERE status='PENDING'")
            return cur.fetchall()
