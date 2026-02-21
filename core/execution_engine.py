import time
import logging
import traceback
import re
from typing import Dict, Any

class ExecutionEngine:
    def __init__(self, bus, executor, logger=None):
        self.bus = bus
        self.executor = executor
        self.logger = logger or logging.getLogger("ExecutionEngine")

    def _safe_float(self, value: Any) -> float:
        if isinstance(value, (int, float)): return float(value)
        if not value: return 0.0
        cleaned = re.sub(r'[^\d,\.]', '', str(value))
        if not cleaned: return 0.0
        if ',' in cleaned and '.' in cleaned:
            if cleaned.rfind(',') > cleaned.rfind('.'):
                cleaned = cleaned.replace('.', '').replace(',', '.')
            else: 
                cleaned = cleaned.replace(',', '')
        elif ',' in cleaned:
            cleaned = cleaned.replace(',', '.')
        try:
            return float(cleaned)
        except ValueError:
            return 0.0

    def process_signal(self, payload: Dict[str, Any], money_manager) -> None:
        self.logger.info(f"⚙️ Avvio processing segnale: {payload.get('teams')}")
        
        tx_id = None
        bet_placed = False
        stake = 0.0

        try:
            if hasattr(self.executor, 'ensure_login'):
                self.executor.ensure_login()

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

            raw_odds = self.executor.find_odds(teams, market)
            odds = self._safe_float(raw_odds)
            if odds <= 0:
                self.bus.emit("BET_FAILED", {"reason": "Odds not found or invalid"})
                return

            stake = self._safe_float(money_manager.get_stake(odds))
            if stake <= 0:
                self.bus.emit("BET_FAILED", {"reason": "Stake zero"})
                return

            real_balance = self._safe_float(self.executor.get_balance())
            if real_balance > 0 and real_balance < stake:
                self.logger.error(f"❌ Saldo bookmaker insufficiente ({real_balance} < {stake})")
                self.bus.emit("BET_FAILED", {"reason": "Insufficient real balance"})
                return

            # 🔴 STEP 1: RESERVE DB
            tx_id = money_manager.reserve(stake)

            # 🔴 STEP 2: PLACE BET (Il crash viene gestito dall'except esterno)
            bet_ok = self.executor.place_bet(teams, market, stake)

            if not bet_ok:
                raise RuntimeError("Bet NON piazzata dal bookmaker. Rifiutata.")

            # 🔴 STEP 3: PUNTO DI NON RITORNO
            bet_placed = True
            
            self.executor.bet_count += 1
            self.logger.info("✅ Scommessa piazzata con successo!")
            
            # 🔴 STEP 4: EMIT EVENTO
            self.bus.emit("BET_SUCCESS", {"tx_id": tx_id, "teams": teams, "stake": stake, "odds": odds})

        except Exception as e:
            self.logger.critical(f"🔥 Crash in Execution Engine: {e}")
            
            # 🔴 GESTIONE ATOMICA UNICA: Rollback solo pre-click.
            if tx_id:
                if not bet_placed:
                    money_manager.refund(tx_id)
                    self.logger.warning(f"🔄 Rollback DB sicuro per TX {tx_id[:8]}. I fondi NON sono passati al bookmaker.")
                else:
                    self.logger.critical(f"☠️ Bet {tx_id[:8]} REALE EFFETTUATA. Nessun rollback.")
                
            if hasattr(self.executor, 'save_blackbox'):
                self.executor.save_blackbox(
                    tx_id, str(e), payload, 
                    stake=stake, quota=odds if 'odds' in locals() else 0, 
                    saldo_db=money_manager.bankroll(), 
                    saldo_book=self.executor.get_balance()
                )
            
            self.bus.emit("BET_FAILED", {"tx_id": tx_id, "reason": str(e)})