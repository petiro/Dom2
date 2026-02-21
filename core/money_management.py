import uuid
import threading
import logging
import math

class MoneyManager:
    def __init__(self, db):
        self.db = db
        self.logger = logging.getLogger("MoneyManager")
        self._lock = threading.RLock()

    def bankroll(self) -> float:
        with self._lock:
            return float(self.db.get_balance())

    def pending(self):
        with self._lock:
            return self.db.pending()

    def reserve(self, amount: float) -> str:
        with self._lock:
            amount = float(amount)
            # 🔴 FIX MATH POISONING: Blocca alla radice NaN, Infinito o negativi
            if math.isnan(amount) or math.isinf(amount) or amount <= 0:
                raise ValueError(f"Stake matematicamente invalido: {amount}")
            
            tx_id = str(uuid.uuid4())
            self.db.reserve(tx_id, amount)
            return tx_id

    def refund(self, tx_id: str) -> None:
        with self._lock:
            self.db.rollback(tx_id)

    def win(self, tx_id: str, payout: float) -> None:
        with self._lock:
            self.db.commit(tx_id, payout)

    def loss(self, tx_id: str) -> None:
        with self._lock:
            self.db.commit(tx_id, 0.0)

    def get_stake(self, odds: float) -> float:
        with self._lock:
            br = self.bankroll()
            stake = min(br * 0.05, 50.0)
            return round(stake, 2)

    def reconcile_balances(self, real_balance: float) -> bool:
        with self._lock:
            current = float(self.bankroll())
            real_balance = float(real_balance)
            if abs(current - real_balance) > 0.01:
                if hasattr(self.db, 'update_bankroll'):
                    self.logger.warning(f"Riconciliazione forzata: DB {current} -> Bookmaker {real_balance}")
                    self.db.update_bankroll(real_balance)
                return True
            return False