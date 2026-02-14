import json
import os
import logging

from core.utils import get_project_root

logger = logging.getLogger("SuperAgent")

_ROOT_DIR = get_project_root()
CONFIG_FILE = os.path.join(_ROOT_DIR, "config", "money_config.json")
ROSERPINA_STATE = os.path.join(_ROOT_DIR, "config", "roserpina_real_state.json")


# --- MOTORE ROSERPINA ---
class RoserpinaEngine:
    def __init__(self, bankroll, target_pct, wins_needed):
        self.bankroll = bankroll
        self.target_pct = target_pct
        self.wins_needed = wins_needed
        self.target_profit_eur = (bankroll * target_pct) / 100
        self.state = {}
        self.load_state()

    def load_state(self):
        if os.path.exists(ROSERPINA_STATE):
            try:
                with open(ROSERPINA_STATE, 'r', encoding='utf-8') as f:
                    self.state = json.load(f)
            except Exception as e:
                logger.warning(f"Errore caricamento stato Roserpina: {e}")
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
            # FIX BUG-15: Log errore invece di silenzio
            logger.error(f"Errore salvataggio stato Roserpina: {e}")

    def calculate_stake(self, odds):
        if odds <= 1.0 or self.state["wins_left"] <= 0:
            return 0.0

        numerator = self.state["current_target"] + self.state["current_loss"]
        denominator = self.state["wins_left"] * (odds - 1)

        if denominator <= 0:
            return 0.0

        stake = numerator / denominator
        # Protezione: Max 25% del capitale per colpo
        return round(min(stake, self.bankroll * 0.25), 2)

    def record_result(self, result, stake, odds):
        if result == "win":
            profit = (stake * odds) - stake
            self.state["current_target"] -= profit
            self.state["wins_left"] -= 1

            if self.state["wins_left"] <= 0 or self.state["current_target"] <= 0.1:
                self.reset_cycle()
                return
        elif result == "lose":
            self.state["current_loss"] += stake

        self.save_state()


# --- MANAGER PRINCIPALE ---
class MoneyManager:
    def __init__(self):
        self.strategy = "Stake Fisso"
        self.fixed_stake = 1.0
        self.bankroll = 100.0
        self.roserpina = None
        self.reload()

    def reload(self):
        self.bankroll = 100.0
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.strategy = data.get("strategy", "Stake Fisso")
                    self.bankroll = float(data.get("bankroll", 100.0))

                    target = float(data.get("target_pct", 45.0))
                    wins = int(data.get("wins_needed", 3))
                    self.roserpina = RoserpinaEngine(self.bankroll, target, wins)

                    self.fixed_stake = 1.0
                    if self.strategy == "Stake Fisso":
                        self.fixed_stake = float(data.get("fixed_amount", 1.0))
            except Exception as e:
                logger.error(f"Errore caricamento config money: {e}")

    def get_stake(self, odds):
        if self.strategy == "Roserpina" and self.roserpina:
            return self.roserpina.calculate_stake(odds)
        return self.fixed_stake

    def record_outcome(self, result, stake, odds):
        if self.strategy == "Roserpina" and self.roserpina:
            self.roserpina.record_result(result, stake, odds)
