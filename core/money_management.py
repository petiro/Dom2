import uuid
import threading
import logging

class MoneyManager:
    def __init__(self, db):
        self.db = db
        self.logger = logging.getLogger("MoneyManager")
        # 🔴 FIX DB LOCK: RLock permette allo stesso thread di richiamare le proprie funzioni senza bloccarsi,
        # ma impedisce a thread esterni (es. la UI) di accavallarsi nelle letture/scritture.
        self._lock = threading.RLock()

    def bankroll(self) -> float:
        with self._lock:
            return float(self.db.get_bankroll())

    def pending(self):
        with self._lock:
            return self.db.pending()

    def reserve(self, amount: float) -> str:
        with self._lock:
            tx_id = str(uuid.uuid4())
            self.db.add_transaction(tx_id, amount, "PENDING")
            return tx_id

    def refund(self, tx_id: str) -> None:
        with self._lock:
            self.db.update_transaction(tx_id, "REFUND")

    def win(self, tx_id: str, payout: float) -> None:
        with self._lock:
            self.db.update_transaction(tx_id, "WIN", payout=payout)

    def loss(self, tx_id: str) -> None:
        with self._lock:
            self.db.update_transaction(tx_id, "LOSS")

    def get_stake(self, odds: float) -> float:
        with self._lock:
            # Calcolo stake base
            br = self.bankroll()
            stake = min(br * 0.05, 50.0) # Protezione massima 5% cassa o 50 euro
            return round(stake, 2)