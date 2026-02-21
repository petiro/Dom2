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

    # 🟠 FIX MEDIO: Sanificazione universale (Punti, Virgole, Valute)
    def _safe_float(self, value: Any) -> float:
        if isinstance(value, (int, float)): return float(value)
        if not value: return 0.0
        cleaned = re.sub(r'[^\d,\.]', '', str(value))
        if not cleaned: return 0.0
        if ',' in cleaned and '.' in cleaned:
            # Stile Europeo: 1.234,56 -> 1234.56
            if cleaned.rfind(',') > cleaned.rfind('.'):
                cleaned = cleaned.replace('.', '').replace(',', '.')
            else: # Stile USA: 1,234.56 -> 1234.56
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
        stake = 0.0
        
        # 🔴 FIX NUCLEARE: Flag di stato transazionale
        bet_placed_on_bookmaker = False

        try:
            # 🟠 FIX MEDIO: Prevenzione bot cieco (Check Login prima di agire)
            if hasattr(self.executor, 'ensure_login'):
                self.executor.ensure_login()

            is_open = self.executor.check_open_bet()
            if not is_open:
                time.sleep(1.5)
                is_open = self.executor.check_open_bet()

            # 🔴 FIX SINTASSI: Aggiunto .db. prima di pending()
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

            # 🔴 FASE 1: TRANSAZIONE DB (RESERVE PRE-CLICK)
            tx_id = money_manager.reserve(stake)

            # 🔴 FASE 2: PIAZZAMENTO REALE SUL BOOKMAKER
            bet_ok = self.executor.place_bet(teams, market, stake)

            if not bet_ok:
                raise RuntimeError("Bet NON piazzata dal bookmaker. Rifiutata.")

            # 🔴 FASE 3: PUNTO DI NON RITORNO
            bet_placed_on_bookmaker = True
            self.executor.bet_count += 1
            self.logger.info("✅ Scommessa piazzata con successo!")
            
            # 🔴 FASE 4: EMIT DELL'EVENTO SOLO A COMMIT AVVENUTO
            self.bus.emit("BET_SUCCESS", {"tx_id": tx_id, "teams": teams, "stake": stake, "odds": odds})

        except Exception as e:
            self.logger.critical(f"🔥 Crash in Execution Engine: {e}\n{traceback.format_exc()}")
            
            # 🔴 FIX NUCLEARE (Il vero Anti-Phantom Refund)
            if tx_id:
                if not bet_placed_on_bookmaker:
                    # Se il bookmaker NON ha preso i soldi, facciamo il Rollback
                    money_manager.refund(tx_id)
                    self.logger.warning(f"🔄 Rollback DB sicuro per TX {tx_id[:8]}.")
                else:
                    # I soldi sono spesi. MAI RIMBORSARE AUTOMATICAMENTE!
                    self.logger.critical(f"☠️ Bet {tx_id[:8]} PIAZZATA ma crash post-click! NO REFUND ESEGUITO. Demandato al Watchdog.")
                
            if hasattr(self.executor, 'save_blackbox'):
                self.executor.save_blackbox(tx_id, str(e), payload, stake=stake, quota=odds if 'odds' in locals() else 0, saldo_db=money_manager.bankroll(), saldo_book=self.executor.get_balance())
            self.bus.emit("BET_FAILED", {"tx_id": tx_id, "reason": str(e)})