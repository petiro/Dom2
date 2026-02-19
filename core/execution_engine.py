import time
import logging

class ExecutionEngine:
    def __init__(self, bus, executor, logger=None):
        self.bus = bus
        self.executor = executor
        self.logger = logger or logging.getLogger("ExecutionEngine")

    def process_signal(self, payload, money_manager):
        self.logger.info(f"⚙️ Avvio processing segnale: {payload.get('teams')}")
        tx_id = None

        try:
            # 🔴 FIX: DOUBLE CHECK ANTI-LAG BET365
            is_open = self.executor.check_open_bet()
            if not is_open:
                time.sleep(1.5) # Attesa popolamento DOM SPA
                is_open = self.executor.check_open_bet()

            if is_open:
                self.logger.warning("⚠️ Bet già aperta su Bet365. Salto segnale.")
                self.bus.emit("BET_FAILED", {"reason": "Bet already open"})
                return

            teams = payload.get("teams")
            market = payload.get("market")

            nav_ok = self.executor.navigate_to_match(teams)
            if not nav_ok:
                self.logger.error("❌ Match non trovato")
                self.bus.emit("BET_FAILED", {"reason": "Match not found"})
                return

            odds = self.executor.find_odds(teams, market)
            if not odds:
                self.logger.error("❌ Quota non trovata")
                self.bus.emit("BET_FAILED", {"reason": "Odds not found"})
                return

            stake = money_manager.get_stake(odds)
            if stake <= 0:
                self.logger.error("❌ Stake zero o bankroll insufficiente")
                self.bus.emit("BET_FAILED", {"reason": "Stake zero"})
                return

            # TRANSAZIONE ACID
            tx_id = money_manager.reserve(stake)

            # ESECUZIONE REALE
            bet_ok = self.executor.place_bet(teams, market, float(stake))

            if bet_ok:
                self.logger.info("✅ Scommessa piazzata con successo!")
                self.bus.emit("BET_SUCCESS", {"tx_id": tx_id, "teams": teams, "stake": float(stake), "odds": odds})
            else:
                self.logger.error("❌ Fallimento piazzamento scommessa")
                self.bus.emit("BET_FAILED", {"tx_id": tx_id, "reason": "Place bet failed"})

        except Exception as e:
            self.logger.critical(f"🔥 Crash in Execution Engine: {e}")
            if hasattr(self.executor, 'save_blackbox'):
                self.executor.save_blackbox(tx_id, str(e), payload)
                
            self.bus.emit("BET_FAILED", {"tx_id": tx_id, "reason": str(e)})
