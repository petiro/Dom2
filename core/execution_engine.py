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
        tx_id = None
        try:
            teams = data.get("teams")
            market = data.get("market")

            if not self.executor.ensure_login():
                raise Exception("Login fallito")

            if not self.executor.navigate_to_match(teams):
                raise Exception("Navigazione fallita")

            odds = self.executor.find_odds(teams, market)
            if odds <= 1.0:
                raise Exception(f"Quota invalida: {odds}")

            stake = money_manager.get_stake(odds)
            if stake <= 0:
                raise Exception("Fondi insufficienti")

            # 3. Transazione ACID
            tx_id = money_manager.reserve(stake)

            if not self.executor.place_bet(teams, market, float(stake)):
                raise Exception("Piazzamento scommessa fallito")

            payout = float(stake) * odds
            
            # 4. Successo
            self.bus.emit(AppEvent.BET_SUCCESS, {
                "tx_id": tx_id,
                "payout": payout,
                "stake": float(stake),
                "odds": odds
            })

        except Exception as e:
            self.log.error(f"Execution Error: {e}")
            self.bus.emit(AppEvent.BET_FAILED, {
                "tx_id": tx_id, 
                "reason": str(e)
            })
