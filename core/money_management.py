import json
import os
import math

# --- FUNZIONI DI UTILITÀ PER I PERCORSI ---
def get_project_root():
    import sys
    if getattr(sys, 'frozen', False): return os.path.dirname(sys.executable)
    try: return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    except: return os.getcwd()

_ROOT_DIR = get_project_root()
# File di configurazione salvato dalla UI (Money Tab)
CONFIG_FILE = os.path.join(_ROOT_DIR, "config", "money_config.json")
# File di stato per memorizzare il ciclo in corso (Resa residua, Prese mancanti)
STATE_FILE = os.path.join(_ROOT_DIR, "config", "roserpina_real_state.json")

# ============================================================================
#  MOTORE ROSERPINA REALE (Logica Sitiscommesse.com)
# ============================================================================
class RoserpinaRealEngine:
    def __init__(self):
        self.load_config()
        self.load_state()

    def load_config(self):
        """Carica Capitale, Target % e Prese dalla configurazione UI"""
        self.bankroll = 100.0
        self.target_pct = 45.0 # Esempio: voglio guadagnare il 45% del capitale
        self.wins_needed = 3   # In 3 scommesse vincenti
        
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    data = json.load(f)
                    self.bankroll = float(data.get("bankroll", 100.0))
                    self.target_pct = float(data.get("target_pct", 45.0))
                    self.wins_needed = int(data.get("wins_needed", 3))
            except Exception as e:
                print(f"Errore caricamento config Roserpina: {e}")
            
        # Calcolo il Profitto Totale Obiettivo in Euro (es. 45€ su 100€)
        self.target_profit_eur = (self.bankroll * self.target_pct) / 100

    def load_state(self):
        """Carica lo stato del ciclo attuale (se esiste) o ne crea uno nuovo"""
        if os.path.exists(STATE_FILE):
            try:
                with open(STATE_FILE, 'r') as f:
                    self.state = json.load(f)
            except: 
                self.reset_cycle()
        else:
            self.reset_cycle()

    def reset_cycle(self):
        """Azzera il ciclo: si riparte con tutto il target da raggiungere"""
        self.state = {
            "current_target": self.target_profit_eur, # Quanto manca da guadagnare (Resa Residua)
            "wins_left": self.wins_needed,            # Quante vittorie mancano (Prese Mancanti)
            "current_loss": 0.0                       # Soldi persi accumulati nel ciclo
        }
        self.save_state()

    def save_state(self):
        """Salva lo stato su disco"""
        try:
            os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
            with open(STATE_FILE, 'w') as f:
                json.dump(self.state, f, indent=4)
        except Exception: pass

    def calculate_stake(self, odds):
        """
        APPLICA LA FORMULA ROSERPINA ORIGINALE:
        Stake = (Target Residuo + Perdite Accumulate) / (Prese Rimaste * (Quota - 1))
        """
        # Controlli di sicurezza
        if odds <= 1.0: return 0.0
        if self.state["wins_left"] <= 0: return 0.0 # Ciclo finito

        numerator = self.state["current_target"] + self.state["current_loss"]
        denominator = self.state["wins_left"] * (odds - 1)
        
        if denominator <= 0: return 0.0 
        
        stake = numerator / denominator
        
        # --- PROTEZIONE BANKROLL ---
        # Evita che il bot punti tutto in una volta se le cose vanno male.
        # Max Stake = 25% del Bankroll totale
        max_stake = self.bankroll * 0.25
        final_stake = round(min(stake, max_stake), 2)
        
        return max(final_stake, 0.10) # Minimo 10 centesimi

    def record_result(self, result, stake, odds):
        """Gestisce l'esito: WIN abbassa il target, LOSE alza il debito"""
        
        if result == "win":
            # Calcolo profitto netto reale
            profit = (stake * odds) - stake
            
            # 1. Abbasso il target residuo di quanto ho appena guadagnato
            self.state["current_target"] -= profit
            # 2. Tolgo una "Presa" (vittoria) dalle mancanti
            self.state["wins_left"] -= 1
            
            # CONTROLLO FINE CICLO
            # Se ho finito le prese O se ho raggiunto l'obiettivo economico (target <= 0)
            if self.state["wins_left"] <= 0 or self.state["current_target"] <= 0.1:
                print(f"🏆 CICLO ROSERPINA COMPLETATO! Profitto incassato.")
                self.reset_cycle()
                return

        elif result == "lose":
            # Ho perso: Aggiungo lo stake perso al mucchio da recuperare
            self.state["current_loss"] += stake
            # Nota: Le "Prese Mancanti" (wins_left) NON cambiano quando perdi.
            # Devi ancora fare lo stesso numero di vittorie, ma recuperando più soldi.
        
        self.save_state()

# ============================================================================
#  MANAGER DI INTERFACCIA (Per il Controller)
# ============================================================================
class MoneyManager:
    def __init__(self, config=None):
        # Inizializzo il motore reale
        self.engine = RoserpinaRealEngine()

    def reload(self):
        """Ricarica la configurazione (chiamato quando premi Salva in UI)"""
        self.engine.load_config()
        # Se i parametri cambiano drasticamente, potresti voler resettare il ciclo,
        # ma per ora manteniamo lo stato per non perdere i progressi.

    def get_stake(self, strategy_name, odds, fixed_amount=None):
        """
        Il controller chiama questo metodo. Ignoriamo 'strategy_name' 
        perché in questa versione usiamo forzatamente Roserpina Reale.
        """
        return self.engine.calculate_stake(odds)

    def record_outcome(self, strategy_name, result, stake, odds=2.0):
        """Registra l'esito nel motore matematico"""
        self.engine.record_result(result, stake, odds)
