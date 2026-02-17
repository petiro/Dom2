import logging
import time
from enum import Enum
from core.events import AppEvent
from core.event_bus import EventBus

class PipelineError(Exception): pass
class ExecutionState(Enum):
    IDLE=0; LOGIN=1; NAVIGATION=2; ANALYSIS=3; TX_START=4; PLACEMENT=5; VERIFICATION=6; COMPLETED=7; FAILED=8

class ExecutionEngine:
    MAX_RETRIES = 3
    RETRY_DELAY = 2.0

    def __init__(self, bus: EventBus, executor):
        self.bus = bus
        self.executor = executor
        self.logger = logging.getLogger("Engine")
        self.state = ExecutionState.IDLE

    def process_signal(self, bet_data, money_manager):
        teams = bet_data.get("teams", "")
        market = bet_data.get("market", "")
        tx_id = None

        try:
            # 1. Login & Navigazione
            self._execute_step(self._login)
            self._execute_step(lambda: self._navigate(teams))

            # 2. Analisi
            self._change_state(ExecutionState.ANALYSIS)
            odds = self.executor.find_odds(teams, market)
            if odds <= 1.0: raise PipelineError(f"Quota invalida: {odds}")

            # 3. Transazione Bancaria (Stabilità 10/10)
            self._change_state(ExecutionState.TX_START)
            stake = money_manager.get_stake(odds)
            if stake <= 0: raise PipelineError("Fondi insufficienti o stake zero")
            
            # PRENOTA I FONDI NEL DB (WAL)
            tx_id = money_manager.reserve_transaction(stake, {"teams": teams, "market": market})
            if not tx_id: raise PipelineError("Fallimento prenotazione fondi DB")

            # 4. Piazzamento
            self._change_state(ExecutionState.PLACEMENT)
            if not self.executor.place_bet(teams, market, float(stake)):
                raise PipelineError("Errore click scommessa")

            # 5. Verifica
            self._change_state(ExecutionState.VERIFICATION)
            if not self.executor.verify_bet_success(teams):
                raise PipelineError("Verifica fallita (Bet non confermata)")

            # 6. Successo
            self._change_state(ExecutionState.COMPLETED)
            payout = float(stake) * odds # Potenziale vincita
            
            # Nota: In un sistema reale, il payout si conferma DOPO la partita.
            # Qui simuliamo il flusso "Bet Piazzata Correttamente".
            # La vincita monetaria vera arriverebbe da un CheckRisultatiWorker.
            # Per ora emettiamo successo tecnico.
            
            self.bus.emit(AppEvent.BET_SUCCESS, {
                "tx_id": tx_id,
                "stake": float(stake),
                "odds": odds,
                "payout": payout # Questo serve solo se la bet è instant-win, altrimenti va gestito asincrono
            })

        except Exception as e:
            self.logger.error(f"Pipeline fail: {e}")
            self._change_state(ExecutionState.FAILED)
            # Passiamo tx_id per permettere il refund
            self.bus.emit(AppEvent.BET_FAILED, {"reason": str(e), "tx_id": tx_id})
        finally:
            self.state = ExecutionState.IDLE

    def _login(self):
        if not self.executor.ensure_login(): raise PipelineError("Login fail")

    def _navigate(self, teams):
        if not self.executor.navigate_to_match(teams): raise PipelineError("Nav fail")

    def _execute_step(self, func):
        for i in range(self.MAX_RETRIES):
            try:
                func()
                return
            except:
                time.sleep(self.RETRY_DELAY)
        raise PipelineError("Step timeout")

    def _change_state(self, new_state):
        self.state = new_state