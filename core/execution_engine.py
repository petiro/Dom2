import time
import logging
from typing import Dict, Any

class ExecutionEngine:
    def __init__(self, bus, executor, logger=None):
        self.bus = bus
        self.executor = executor
        self.logger = logger or logging.getLogger("ExecutionEngine")

    def process_signal(self, payload: Dict[str, Any], money_manager) -> None:
        self.logger.info(f"⚙️ Avvio processing segnale: {payload.get('teams')}")
        tx_id = None
        stake = 0.0

        try:
            is_open = self.executor.check_open_bet()
            if not is_open:
                time.sleep(1.5)
                is_open = self.executor.check_open_bet()

            if money_manager.db.pending() or is_open:
                self.logger.warning("⚠️ Bet già aperta o pending. Salto segnale.")
                self.bus.emit("BET_FAILED", {"reason": "Bet already open"})
                return

            teams = payload.get("teams", "")
            market = payload.get("market", "")

            nav_ok = self.executor.navigate_to_match(teams)
            if not nav_ok:
                self.bus.emit("BET_FAILED", {"reason": "Match not found"})
                return

            odds = self.executor.find_odds(teams, market)
            if not odds:
                self.bus.emit("BET_FAILED", {"reason": "Odds not found"})
                return

            stake = float(money_manager.get_stake(odds))
            if stake <= 0:
                self.bus.emit("BET_FAILED", {"reason": "Stake zero"})
                return

            real_balance = self.executor.get_balance()
            if real_balance is not None and real_balance < stake:
                self.logger.error(f"❌ Saldo bookmaker insufficiente ({real_balance} < {stake})")
                self.bus.emit("BET_FAILED", {"reason": "Insufficient real balance"})
                return

            tx_id = money_manager.reserve(stake)

            bet_ok = self.executor.place_bet(teams, market, stake)

            if not bet_ok:
                self.logger.error("❌ Fallimento piazzamento scommessa")
                money_manager.refund(tx_id)
                self.bus.emit("BET_FAILED", {"tx_id": tx_id, "reason": "Place bet failed"})
                return

            self.executor.bet_count += 1
            self.logger.info("✅ Scommessa piazzata con successo!")
            self.bus.emit("BET_SUCCESS", {"tx_id": tx_id, "teams": teams, "stake": stake, "odds": odds})

        except Exception as e:
            self.logger.critical(f"🔥 Crash in Execution Engine: {e}")
            if tx_id:
                money_manager.refund(tx_id)
                
            if hasattr(self.executor, 'save_blackbox'):
                self.executor.save_blackbox(
                    tx_id, str(e), payload,
                    stake=stake, quota=odds if 'odds' in locals() else 0,
                    saldo_db=money_manager.bankroll(),
                    saldo_book=self.executor.get_balance()
                )
            self.bus.emit("BET_FAILED", {"tx_id": tx_id, "reason": str(e)})