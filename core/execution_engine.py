import logging
import time
from core.events import AppEvent
from core.event_bus import bus

class ExecutionEngine:
    def __init__(self, bus, executor):
        self.bus = bus
        self.executor = executor
        self.log = logging.getLogger("Engine")

    def process_signal(self, data, money_manager):
        """
        Processa un segnale di scommessa con logica ACID V8.4.
        """
        tx_id = None
        teams = data.get("teams", "Unknown")
        market = data.get("market", "Unknown")
        
        self.log.info(f"🤖 Processing Signal: {teams} @ {market}")

        try:
            # 1. CONTROLLI PRELIMINARI
            if not self.executor.ensure_login():
                raise Exception("Login check failed")

            if not self.executor.navigate_to_match(teams):
                raise Exception(f"Match not found: {teams}")

            # 2. LETTURA QUOTE & VALIDAZIONE
            odds = self.executor.find_odds(teams, market)
            
            if odds < 1.01 or odds > 50.0:
                raise Exception(f"Invalid odds detected: {odds}")

            # 3. CALCOLO STAKE
            stake = money_manager.get_stake(odds)
            if stake <= 0:
                raise Exception("Insufficient funds or invalid stake logic")

            self.log.info(f"💰 Validated: Odds {odds} | Stake {stake}€")

            # 4. TRANSAZIONE ACID
            # Qui money_manager.reserve ora ritorna correttamente tx_id (UUID)
            tx_id = money_manager.reserve(stake)

            # 5. ESECUZIONE BET
            if not self.executor.place_bet(teams, market, float(stake)):
                raise Exception("Place bet button click failed")

            # 6. VERIFICA FINALE
            if not self.executor.verify_bet_success(teams):
                 raise Exception("Bet verification failed (No confirmation)")

            # 7. SUCCESSO
            payout = float(stake) * odds
            self.bus.emit(AppEvent.BET_SUCCESS, {
                "tx_id": tx_id,
                "payout": payout,
                "stake": float(stake),
                "odds": odds,
                "teams": teams
            })
            self.log.info(f"✅ BET PLACED: {teams} | {stake}€ @ {odds}")

        except Exception as e:
            self.log.error(f"❌ Execution Fail: {e}")
            
            # ROLLBACK SICURO
            self.bus.emit(AppEvent.BET_FAILED, {
                "tx_id": tx_id, 
                "reason": str(e),
                "teams": teams
            })