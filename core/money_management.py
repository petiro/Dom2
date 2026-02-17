import json
import os
import logging
import threading
from decimal import Decimal, ROUND_DOWN
from core.config_paths import MONEY_CONFIG_FILE


class MoneyManager:
    def __init__(self):
        self.logger = logging.getLogger("Money")
        self.strategy = "Stake Fisso"
        self.bankroll = Decimal("100.00")
        self._lock = threading.Lock()
        self.reload()

    def reload(self):
        with self._lock:
            try:
                if os.path.exists(MONEY_CONFIG_FILE):
                    with open(MONEY_CONFIG_FILE) as f:
                        data = json.load(f)
                        self.bankroll = Decimal(str(data.get("bankroll", 100.0)))
                else:
                    self.bankroll = Decimal("100.00")
            except Exception:
                self.bankroll = Decimal("100.00")

    # 🔥 Stake reale: 2% bankroll con cap 25%
    def get_stake(self, odds):
        with self._lock:
            stake = self.bankroll * Decimal("0.02")
            cap = self.bankroll * Decimal("0.25")
            stake = min(stake, cap)
            return float(stake.quantize(Decimal("0.01"), rounding=ROUND_DOWN))

    def record_outcome(self, result, stake, odds):
        with self._lock:
            s = Decimal(str(stake))
            o = Decimal(str(odds))

            limit = self.bankroll * Decimal("0.25")
            if s > limit:
                self.logger.error(f"⛔ STAKE {s} > 25% BANKROLL ({limit}). BLOCCATA.")
                raise ValueError("Stake exceeds 25% bankroll limit")

            if result == "win":
                self.bankroll += (s * o) - s
            elif result == "lose":
                self.bankroll -= s

            if self.bankroll < 0:
                self.logger.critical("NEGATIVE BANKROLL! RESET TO 0.")
                self.bankroll = Decimal("0.00")

            self.bankroll = self.bankroll.quantize(
                Decimal("0.01"), rounding=ROUND_DOWN
            )

            self._save()

    def _save(self):
        try:
            with open(MONEY_CONFIG_FILE, "w") as f:
                json.dump({"bankroll": float(self.bankroll)}, f)
        except Exception:
            self.logger.error("Failed saving bankroll")

    def get_bankroll(self):
        with self._lock:
            return float(self.bankroll)