import uuid
import logging
from decimal import Decimal, ROUND_DOWN
from core.database import Database

class MoneyManager:
    def __init__(self):
        self.db = Database()
        self.logger = logging.getLogger("Money")

    def get_stake(self, odds):
        try:
            bal = self.db.get_balance()
            
            # Strategia 2%
            stake = bal * Decimal("0.02")
            cap = bal * Decimal("0.25")
            stake = min(stake, cap)

            if stake < Decimal("0.50"):
                stake = Decimal("0.50")

            if stake > bal:
                return Decimal("0.00")

            return stake.quantize(Decimal("0.01"), rounding=ROUND_DOWN)
        except:
            return Decimal("0.00")

    def reserve(self, amount):
        tx = str(uuid.uuid4())
        self.db.reserve(tx, amount)
        return tx

    def win(self, tx, payout):
        self.db.commit(tx, payout)

    def loss(self, tx):
        self.db.commit(tx, 0)

    def refund(self, tx):
        self.db.rollback(tx)

    def bankroll(self):
        return float(self.db.get_balance())
