import json
import os
import logging
import threading

from core.utils import get_project_root

logger = logging.getLogger("SuperAgent")

_ROOT_DIR = get_project_root()
CONFIG_FILE = os.path.join(_ROOT_DIR, "config", "money_config.json")
ROSERPINA_STATE = os.path.join(_ROOT_DIR, "config", "roserpina_real_state.json")


# --- ROSERPINA ENGINE ---
class RoserpinaEngine:
    def __init__(self, bankroll, target_pct, wins_needed, max_bet_pct=0.25):
        self.bankroll = bankroll
        self.target_pct = target_pct
        self.wins_needed = wins_needed
        self.max_bet_pct = max_bet_pct
        self.target_profit_eur = (bankroll * target_pct) / 100
        self.state = {}
        self.load_state()

    def load_state(self):
        if os.path.exists(ROSERPINA_STATE):
            try:
                with open(ROSERPINA_STATE, 'r', encoding='utf-8') as f:
                    self.state = json.load(f)
            except Exception as e:
                logger.warning(f"Error loading Roserpina state: {e}")
                self.reset_cycle()
        else:
            self.reset_cycle()

    def reset_cycle(self):
        self.state = {
            "current_target": self.target_profit_eur,
            "wins_left": self.wins_needed,
            "current_loss": 0.0
        }
        self.save_state()

    def save_state(self):
        try:
            os.makedirs(os.path.dirname(ROSERPINA_STATE), exist_ok=True)
            with open(ROSERPINA_STATE, 'w', encoding='utf-8') as f:
                json.dump(self.state, f, indent=4)
        except Exception as e:
            logger.error(f"Error saving Roserpina state: {e}")

    def calculate_stake(self, odds):
        if odds <= 1.0 or self.state["wins_left"] <= 0:
            return 0.0

        numerator = self.state["current_target"] + self.state["current_loss"]
        denominator = self.state["wins_left"] * (odds - 1)

        if denominator <= 0:
            return 0.0

        stake = numerator / denominator
        # Protection: cap stake at max_bet_pct of bankroll
        return round(min(stake, self.bankroll * self.max_bet_pct), 2)

    def record_result(self, result, stake, odds):
        if result == "win":
            profit = (stake * odds) - stake
            self.state["current_target"] -= profit
            self.state["wins_left"] -= 1

            if self.state["wins_left"] <= 0 or self.state["current_target"] < 0.01:
                self.reset_cycle()
                return
        elif result == "lose":
            self.state["current_loss"] += stake

        self.save_state()


# --- MAIN MANAGER ---
class MoneyManager:
    def __init__(self):
        self._lock = threading.Lock()
        self.strategy = "Stake Fisso"
        self.fixed_stake = 1.0
        self.bankroll = 100.0
        self.roserpina = None
        self.reload()

    def reload(self):
        with self._lock:
            if not os.path.exists(CONFIG_FILE):
                # Reset to defaults when config file is missing
                self.strategy = "Stake Fisso"
                self.fixed_stake = 1.0
                self.bankroll = 100.0
                self.roserpina = None
                return

            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                # Parse into temp vars first — only assign on success
                strategy = data.get("strategy", "Stake Fisso")
                bankroll = float(data.get("bankroll", 100.0))
                target = float(data.get("target_pct", 45.0))
                wins = int(data.get("wins_needed", 3))
                max_bet = float(data.get("max_bet_pct", 0.25))
                fixed_stake = 1.0
                if strategy == "Stake Fisso":
                    fixed_stake = float(data.get("fixed_amount", 1.0))

                # All parsed OK — now commit
                self.strategy = strategy
                self.bankroll = bankroll
                self.fixed_stake = fixed_stake
                self.roserpina = RoserpinaEngine(bankroll, target, wins, max_bet)

            except Exception as e:
                logger.error(f"Error loading money config: {e}")

    def get_stake(self, odds):
        with self._lock:
            if self.strategy == "Roserpina" and self.roserpina:
                return self.roserpina.calculate_stake(odds)
            return self.fixed_stake

    def get_bankroll(self):
        """Return current bankroll value."""
        with self._lock:
            return self.bankroll

    def record_outcome(self, result, stake, odds):
        with self._lock:
            if self.strategy == "Roserpina" and self.roserpina:
                self.roserpina.record_result(result, stake, odds)
