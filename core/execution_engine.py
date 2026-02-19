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
            # 1. BLOCCO SE BET APERTA
            if self.executor.check_open_bet():
                self.logger.warning("⚠️ Bet già aperta su Bet365. Salto.")
                self.bus.emit("BET_FAILED", {"reason": "Bet already open"})
                return

            teams = payload.get("teams")
            market = payload.get("market")

            # 2. NAVIGAZIONE
            nav_ok = self.executor.navigate_to_match(teams)
            if not nav_ok:
                self.logger.error("❌ Match non trovato")
                self.bus.emit("BET_FAILED", {"reason": "Match not found"})
                return

            # 3. QUOTA
            odds = self.executor.find_odds(teams, market)
            if not odds:
                self.logger.error("❌ Quota non trovata")
                self.bus.emit("BET_FAILED", {"reason": "Odds not found"})
                return

            stake = getattr(money_manager, "current_stake", 2.0)

            # 🔴 FIX CRITICO — PRENOTAZIONE DB (ACID TRANSACTIONS)
            tx_id = money_manager.reserve(stake)

            # 4. ESECUZIONE REALE
            bet_ok = self.executor.place_bet(teams, market, stake)

            if bet_ok:
                self.logger.info("✅ Scommessa piazzata con successo!")
                self.bus.emit("BET_SUCCESS", {
                    "tx_id": tx_id,
                    "teams": teams,
                    "stake": stake,
                    "odds": odds
                })
            else:
                self.logger.error("❌ Fallimento piazzamento scommessa")
                self.bus.emit("BET_FAILED", {
                    "tx_id": tx_id,
                    "reason": "Place bet failed"
                })

        except Exception as e:
            self.logger.critical(f"🔥 Crash in Execution Engine: {e}")
            self.bus.emit("BET_FAILED", {
                "tx_id": tx_id,
                "reason": str(e)
            })