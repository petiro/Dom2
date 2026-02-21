import uuid
import threading
import logging

class MoneyManager:
    def __init__(self, db):
        self.db = db
        self.logger = logging.getLogger("MoneyManager")
        # 🔴 FIX DB LOCK: RLock impedisce l'Overspending Simultaneo
        self._lock = threading.RLock()

    def bankroll(self) -> float:
        with self._lock:
            # 🔴 FIX: Ora chiama correttamente get_balance() del DB
            return float(self.db.get_balance())

    def pending(self):
        with self._lock:
            # Questo era già corretto
            return self.db.pending()

    def reserve(self, amount: float) -> str:
        with self._lock:
            tx_id = str(uuid.uuid4())
            # 🔴 FIX: Ora usa la funzione reserve() del DB invece di add_transaction
            self.db.reserve(tx_id, amount)
            return tx_id

    def refund(self, tx_id: str) -> None:
        with self._lock:
            # 🔴 FIX: Ora usa rollback() che ripristina i fondi nel tuo DB
            self.db.rollback(tx_id)

    def win(self, tx_id: str, payout: float) -> None:
        with self._lock:
            # 🔴 FIX: Usa commit() per confermare la vincita
            self.db.commit(tx_id, payout)

    def loss(self, tx_id: str) -> None:
        with self._lock:
            # 🔴 FIX: Usa commit() con payout 0 per segnare la sconfitta
            self.db.commit(tx_id, 0.0)

    def get_stake(self, odds: float) -> float:
        with self._lock:
            # Calcolo stake base
            br = self.bankroll()
            stake = min(br * 0.05, 50.0) # Protezione massima 5% cassa o 50 euro
            return round(stake, 2)
