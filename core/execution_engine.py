import time
import logging

class ExecutionEngine:
    def __init__(self, bus, executor, logger=None):
        self.bus = bus
        self.executor = executor
        self.logger = logger or logging.getLogger("ExecutionEngine")

    def process_signal(self, payload, money_manager):
        self.logger.info(f"⚙️ Avvio processing segnale: {payload.get('teams')}")
        
        try:
            # 🔴 FIX 2 — BLOCCO SE BET APERTA
            if self.executor.check_open_bet():
                self.logger.warning("⚠️ Bet già aperta su Bet365. Salto segnale.")
                self.bus.publish("BET_FAILED", {"reason": "Bet already open"}) # Sblocca il lock
                return

            teams = payload.get("teams")
            market = payload.get("market")
            
            nav_ok = self.executor.navigate_to_match(teams)
            if not nav_ok:
                self.logger.error("❌ Match non trovato")
                self.bus.publish("BET_FAILED", {"reason": "Match not found"})
                return

            odds = self.executor.find_odds(teams, market)
            if not odds:
                self.logger.error("❌ Quota non trovata")
                self.bus.publish("BET_FAILED", {"reason": "Odds not found"})
                return

            stake = money_manager.current_stake

            # Esecuzione Reale
            bet_ok = self.executor.place_bet(teams, market, stake)
            
            if bet_ok:
                self.logger.info("✅ Scommessa piazzata con successo!")
                self.bus.publish("BET_SUCCESS", {"teams": teams, "stake": stake, "odds": odds})
            else:
                self.logger.error("❌ Fallimento piazzamento scommessa")
                self.bus.publish("BET_FAILED", {"reason": "Place bet failed"})

        except Exception as e:
            # 🔴 FIX 1: GARANZIA SBLOCCO LOCK IN CASO DI CRASH
            self.logger.critical(f"🔥 Crash in Execution Engine: {e}")
            self.bus.publish("BET_FAILED", {"reason": str(e)})