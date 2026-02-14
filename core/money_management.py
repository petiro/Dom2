import json
import os

def get_project_root():
    import sys
    if getattr(sys, 'frozen', False): return os.path.dirname(sys.executable)
    try: return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    except: return os.getcwd()

_ROOT_DIR = get_project_root()
CONFIG_FILE = os.path.join(_ROOT_DIR, "config", "money_config.json")
ROSERPINA_STATE = os.path.join(_ROOT_DIR, "config", "roserpina_state.json")

# --- MOTORE ROSERPINA ---
class RoserpinaEngine:
    def __init__(self, bankroll, target_pct, wins_needed):
        self.bankroll = bankroll
        self.target_pct = target_pct
        self.wins_needed = wins_needed
        self.target_profit_eur = (bankroll * target_pct) / 100
        self.load_state()

    def load_state(self):
        if os.path.exists(ROSERPINA_STATE):
            try:
                with open(ROSERPINA_STATE, 'r') as f:
                    self.state = json.load(f)
            except: self.reset_cycle()
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
            with open(ROSERPINA_STATE, 'w') as f: json.dump(self.state, f, indent=4)
        except: pass

    def calculate_stake(self, odds):
        if odds <= 1.0 or self.state["wins_left"] <= 0: return 0.0
        numerator = self.state["current_target"] + self.state["current_loss"]
        denominator = self.state["wins_left"] * (odds - 1)
        if denominator <= 0: return 0.0
        
        stake = numerator / denominator
        # Protezione 25% Bankroll
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
        self.roserpina = None
        self.reload()

    def reload(self):
        """Carica config da UI"""
        self.bankroll = 100.0
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    data = json.load(f)
                    self.strategy = data.get("strategy", "Stake Fisso")
                    self.bankroll = float(data.get("bankroll", 100.0))
                    
                    # Config Roserpina
                    target = float(data.get("target_pct", 45.0))
                    wins = int(data.get("wins_needed", 3))
                    self.roserpina = RoserpinaEngine(self.bankroll, target, wins)
                    
                    # Config Stake Fisso (lo usiamo se la strategia è Stake Fisso)
                    # Possiamo usare un campo specifico o calcolarlo come %
                    self.fixed_stake = 1.0 # Default fallback
                    if self.strategy == "Stake Fisso":
                        # Se l'utente usa il campo 'target_pct' come importo fisso in UI
                        # oppure puoi aggiungere un campo 'fixed_amount' nel JSON
                        self.fixed_stake = float(data.get("fixed_amount", 1.0)) 
            except: pass

    def get_stake(self, odds):
        if self.strategy == "Roserpina" and self.roserpina:
            return self.roserpina.calculate_stake(odds)
        else:
            return self.fixed_stake

    def record_outcome(self, result, stake, odds):
        if self.strategy == "Roserpina" and self.roserpina:
            self.roserpina.record_result(result, stake, odds)
