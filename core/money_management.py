import json
import os
import logging
from decimal import Decimal, ROUND_DOWN
from core.config_paths import MONEY_CONFIG_FILE

class MoneyManager:
    def __init__(self):
        self.logger = logging.getLogger("Money")
        self.strategy = "Stake Fisso"
        self.bankroll = Decimal("100.00")
        self.reload()

    def reload(self):
        try:
            if os.path.exists(MONEY_CONFIG_FILE):
                with open(MONEY_CONFIG_FILE) as f:
                    data = json.load(f)
                    self.bankroll = Decimal(str(data.get("bankroll", 100.0)))
            else:
                self.bankroll = Decimal("100.00")
        except: self.bankroll = Decimal("100.00")

    def get_stake(self, odds): return 1.0

    def record_outcome(self, result, stake, odds):
        s = Decimal(str(stake))
        o = Decimal(str(odds))
        
        if s > self.bankroll * Decimal("0.25"):
            self.logger.warning("Stake > 25% bankroll!")

        if result == "win": self.bankroll += (s * o) - s
        elif result == "lose": self.bankroll -= s
        
        if self.bankroll < 0:
            self.logger.critical("NEGATIVE BANKROLL DETECTED!")
            self.bankroll = Decimal("0.00")
            
        self.bankroll = self.bankroll.quantize(Decimal("0.01"), rounding=ROUND_DOWN)
        self._save()

    def _save(self):
        try:
            with open(MONEY_CONFIG_FILE, 'w') as f:
                json.dump({"bankroll": float(self.bankroll)}, f)
        except: pass
        
    def get_bankroll(self): return float(self.bankroll)