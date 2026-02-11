import json
import os

_ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

class RoserpinaTable:
    def __init__(self, table_id=1, bankroll=100.0, target_pct=3.0, max_bets=10):
        self.config_path = os.path.join(_ROOT_DIR, "config", f"money_table_{table_id}.json")
        self.bankroll = bankroll
        self.target_profit = (bankroll * target_pct) / 100
        self.max_bets = max_bets
        self.data = self._load_or_init()
        self.is_pending = False

    def _load_or_init(self):
        if os.path.exists(self.config_path):
            with open(self.config_path, 'r') as f:
                return json.load(f)
        return self._reset_data()

    def _reset_data(self):
        data = {
            "current_debt": 0.0,
            "bets_count": 0,
            "consecutive_losses": 0
        }
        self._save(data)
        return data

    def _save(self, data=None):
        if data: self.data = data
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        with open(self.config_path, 'w') as f:
            json.dump(self.data, f, indent=4)

    def calculate_stake(self, odds):
        if odds <= 1.0: return 0.0
        # Formula Roserpina: (Obiettivo + Debito) / (Quota - 1)
        needed = self.target_profit + self.data["current_debt"]
        stake = needed / (odds - 1)
        # Safety: Max 50% del bankroll
        return round(min(stake, self.bankroll * 0.5), 2)

    def record_result(self, result, stake):
        """ result: 'win' o 'lose' """
        if result == "win":
            self._reset_data() # Ciclo chiuso, profitto incassato
        elif result == "lose":
            self.data["current_debt"] += stake
            self.data["bets_count"] += 1
            self.data["consecutive_losses"] += 1
            
            # Reset forzato se troppe perdite o fine ciclo
            if (self.data["bets_count"] >= self.max_bets or 
                self.data["consecutive_losses"] >= 3):
                self._reset_data()
            else:
                self._save()
        
        self.is_pending = False
