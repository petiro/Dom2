import time
import logging
import traceback
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
        
        # 🔴 FIX NUCLEARE: Flag per impedire il Phantom Refund
        bet_placed_on_bookmaker = False

        try:
            is_open = self.executor.check_open_bet()
            if not is_open:
                time.sleep(1.5)
                is_open = self.executor.check_open_bet()

            if money_manager.pending() or is_open:
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

            # 1. Riserva soldi nel DB
            tx_id = money_manager.reserve(stake)

            # 2. Piazza sul bookmaker
            bet_ok = self.executor.place_bet(teams, market, stake)

            if not bet_ok:
                raise RuntimeError("Bet NON piazzata dal bookmaker. Rifiutata.")

            # 🔴 PUNTO DI NON RITORNO: I SOLDI SONO SUL SITO.
            bet_placed_on_bookmaker = True

            self.executor.bet_count += 1
            self.logger.info("✅ Scommessa piazzata con successo!")
            
            # 3. Emetti successo
            self.bus.emit("BET_SUCCESS", {"tx_id": tx_id, "teams": teams, "stake": stake, "odds": odds})

        except Exception as e:
            self.logger.critical(f"🔥 Crash in Execution Engine: {e}\n{traceback.format_exc()}")
            
            # 🔴 FIX NUCLEARE: Rollback SOLO se il bookmaker NON ha preso i soldi
            if tx_id:
                if not bet_placed_on_bookmaker:
                    money_manager.refund(tx_id)
                    self.logger.warning(f"🔄 Rollback DB eseguito per TX {tx_id[:8]} (Nessun fondo reale mosso).")
                else:
                    self.logger.critical(f"☠️ Bet {tx_id[:8]} PIAZZATA REALE ma crash interno! NO REFUND eseguito. Ledger salvo.")
                
            if hasattr(self.executor, 'save_blackbox'):
                self.executor.save_blackbox(
                    tx_id, str(e), payload,
                    stake=stake, quota=odds if 'odds' in locals() else 0,
                    saldo_db=money_manager.bankroll(),
                    saldo_book=self.executor.get_balance()
                )
            self.bus.emit("BET_FAILED", {"tx_id": tx_id, "reason": str(e)})