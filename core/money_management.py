import uuid
import logging
from decimal import Decimal, ROUND_DOWN

class MoneyManager:
    def __init__(self, db):
        self.db = db
        self.logger = logging.getLogger("Money")

    def get_stake(self, odds):
        try:
            bal = Decimal(str(self.db.get_balance()))
            if bal <= Decimal("0.00"): 
                return Decimal("0.00")

            stake = bal * Decimal("0.02")
            cap = bal * Decimal("0.25")
            stake = min(stake, cap)

            if stake < Decimal("0.50"): stake = Decimal("0.50")
            if stake > bal: return Decimal("0.00")

            return stake.quantize(Decimal("0.01"), rounding=ROUND_DOWN)
        except Exception as e:
            self.logger.error(f"Stake calc error: {e}")
            return Decimal("0.00")

    def reserve(self, amount):
        tx = str(uuid.uuid4())
        self.db.reserve(tx, amount)
        self.logger.info(f"🔒 Prenotati {amount}€ nel DB (TX: {tx[:8]})")
        return tx

    def win(self, tx, payout):
        try: self.db.commit(tx, payout)
        except Exception as e: self.logger.error(f"Win commit error: {e}")

    def loss(self, tx):
        try: self.db.commit(tx, 0)
        except Exception as e: self.logger.error(f"Loss commit error: {e}")

    def refund(self, tx):
        try: self.db.rollback(tx)
        except Exception as e: self.logger.error(f"Refund error: {e}")

    def bankroll(self):
        try: return float(self.db.get_balance())
        except Exception: return 0.0