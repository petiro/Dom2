import logging
import uuid
from decimal import Decimal, ROUND_DOWN
from core.database import Database

class MoneyManager:
    def __init__(self):
        self.logger = logging.getLogger("MoneyManager")
        self.db = Database() # Singleton
        self.strategy = "Dynamic 2%"

    def get_stake(self, odds):
        # Calcola stake basandosi sul saldo REALE nel DB
        balance = self.db.get_balance()
        
        # Strategy: 2% del saldo, Max 25% del saldo
        stake = balance * Decimal("0.02")
        cap = balance * Decimal("0.25")
        stake = min(stake, cap)
        
        # Hard floor 0.50€
        if stake < Decimal("0.50"):
            stake = Decimal("0.50")
            
        # Se non ho abbastanza soldi nemmeno per il floor
        if stake > balance:
            return Decimal("0.00")

        return stake.quantize(Decimal("0.01"), rounding=ROUND_DOWN)

    def reserve_transaction(self, amount, details):
        """Crea una transazione univoca (TXID) e blocca i fondi."""
        tx_id = str(uuid.uuid4())
        try:
            self.db.reserve_funds(tx_id, amount, details)
            self.logger.info(f"💸 Funds reserved for TX {tx_id[:8]}: {amount}€")
            return tx_id
        except ValueError:
            self.logger.error("❌ Insufficient funds for reservation.")
            return None
        except Exception as e:
            self.logger.critical(f"❌ DB Transaction Error: {e}")
            return None

    def confirm_win(self, tx_id, payout):
        self.db.commit_transaction(tx_id, profit=payout)
        self.logger.info(f"💰 Win confirmed TX {tx_id[:8]}. Payout: {payout}€")

    def confirm_loss(self, tx_id):
        self.db.commit_transaction(tx_id, profit=0)
        self.logger.info(f"📉 Loss confirmed TX {tx_id[:8]}.")

    def refund(self, tx_id):
        self.db.rollback_transaction(tx_id)
        self.logger.warning(f"↩️ Refunded TX {tx_id[:8]}.")

    def get_bankroll(self):
        return float(self.db.get_balance())