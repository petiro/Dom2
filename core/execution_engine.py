import time
from enum import Enum
from core.event_bus import bus


class State(Enum):
    IDLE = 0
    LOGIN_CHECK = 1
    NAVIGATING = 2
    ANALYZING_MARKET = 3
    PLACING_BET = 4
    VERIFYING = 5
    RETRY_WAIT = 98
    ERROR_FATAL = 99


class ExecutionEngine:

    MAX_RETRIES = 3
    RETRY_DELAY = 5

    def __init__(self, executor, worker, logger):
        self.executor = executor
        self.worker = worker
        self.logger = logger
        self.current_state = State.IDLE

    def process_signal(self, bet_data, money_manager):
        self.worker.submit(self._pipeline_task, bet_data, money_manager)

    def _pipeline_task(self, bet_data, money_manager):
        executor = self.executor
        try:
            selectors = executor._load_selectors()

            # LOGIN
            if not self._execute_step(
                State.LOGIN_CHECK,
                executor.ensure_login,
                selectors
            ):
                raise Exception("Login failed after retries")

            # NAVIGAZIONE
            teams = bet_data.get("teams", "")
            market = bet_data.get("market", "")

            if not self._execute_step(
                State.NAVIGATING,
                executor.navigate_to_match,
                teams,
                selectors
            ):
                home = selectors.get("home_logo", "a.logo")
                executor.human_click(home)
                raise Exception("Navigation failed")

            # ANALISI QUOTA
            self._set_state(State.ANALYZING_MARKET)

            odds = executor.find_odds(teams, market)

            if not odds or odds <= 1.0:
                raise Exception("Invalid odds")

            stake = money_manager.get_stake(odds)
            if stake <= 0:
                self.logger.warning("Stake 0. Skip.")
                return

            # PIAZZAMENTO
            self._set_state(State.PLACING_BET)

            if not executor.place_bet(teams, market, stake):
                raise Exception("Bet placement failed")

            # VERIFICA
            self._set_state(State.VERIFYING)

            if executor.verify_bet_success(teams):
                bus.emit("BET_SUCCESS", {
                    "data": bet_data,
                    "stake": stake,
                    "odds": odds
                })
            else:
                bus.emit("BET_UNKNOWN", "Placed but not confirmed")

        except Exception as e:
            self.logger.error(f"Pipeline Error: {e}")
            bus.emit("BET_FAILED", str(e))

        finally:
            self._set_state(State.IDLE)

    def _execute_step(self, state, func, *args):
        self._set_state(state)

        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                if func(*args):
                    return True
            except Exception as e:
                self.logger.warning(
                    f"Step {state.name} error: {e}"
                )

            if attempt < self.MAX_RETRIES:
                self.logger.info(
                    f"Retry {state.name} ({attempt}/{self.MAX_RETRIES})"
                )
                self._set_state(State.RETRY_WAIT)
                time.sleep(self.RETRY_DELAY)
                self._set_state(state)

        return False

    def _set_state(self, new_state):
        self.current_state = new_state
        bus.emit("STATE_CHANGE", new_state.name)
