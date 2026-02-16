import logging
import time
from enum import Enum
from typing import Any

from core.events import AppEvent
from core.event_bus import EventBus


# ==========================================================
# Custom Exceptions
# ==========================================================

class PipelineError(Exception):
    """Base class for pipeline-related errors."""
    pass


class LoginFailedError(PipelineError):
    pass


class NavigationFailedError(PipelineError):
    pass


class PlacementFailedError(PipelineError):
    pass


class VerificationFailedError(PipelineError):
    pass


# ==========================================================
# Execution State Enum
# ==========================================================

class ExecutionState(Enum):
    IDLE = 0
    LOGIN = 1
    NAVIGATION = 2
    ANALYSIS = 3
    PLACEMENT = 4
    VERIFICATION = 5
    COMPLETED = 6
    FAILED = 7
    RETRY_WAIT = 99


# ==========================================================
# Execution Engine (Senior Grade)
# ==========================================================

class ExecutionEngine:
    """
    Event-driven state machine pipeline.
    Orchestrates the workflow without knowing implementation details.

    The executor is responsible for loading its own config/selectors.
    The engine only passes business data (teams, market, stake).
    """

    MAX_RETRIES = 3
    RETRY_DELAY = 3.0

    def __init__(self, bus: EventBus, executor: Any):
        self.bus = bus
        self.executor = executor
        self.logger = logging.getLogger(self.__class__.__name__)
        self.state = ExecutionState.IDLE

    # ======================================================
    # Public API
    # ======================================================

    def process_signal(self, bet_data: dict, money_manager: Any):
        """
        Entry point for the execution pipeline.
        Should be called inside a worker thread to avoid blocking UI.
        """
        teams = bet_data.get("teams", "")
        market = bet_data.get("market", "")

        try:
            # 1. Login
            self._execute_step_with_retry(
                ExecutionState.LOGIN,
                self._login
            )

            # 2. Navigation
            self._execute_step_with_retry(
                ExecutionState.NAVIGATION,
                self._navigate,
                teams
            )

            # 3. Analysis (Odds)
            self._change_state(ExecutionState.ANALYSIS)
            odds = self._analyze(teams, market)

            # 4. Money Management
            stake = money_manager.get_stake(odds)
            if stake <= 0:
                self.logger.warning("Stake calculated as 0 or negative. Aborting.")
                self._change_state(ExecutionState.IDLE)
                return

            # 5. Placement
            self._change_state(ExecutionState.PLACEMENT)
            self._place(teams, market, stake)

            # 6. Verification
            self._change_state(ExecutionState.VERIFICATION)
            self._verify(teams)

            # Success
            self._change_state(ExecutionState.COMPLETED)
            self.bus.emit(AppEvent.BET_SUCCESS, {
                "data": bet_data,
                "stake": stake,
                "odds": odds
            })

        except PipelineError as e:
            self._handle_failure(str(e))

        except Exception as e:
            self.logger.exception("Unexpected pipeline crash")
            self.bus.emit(AppEvent.BET_ERROR, {"reason": str(e)})
            self._change_state(ExecutionState.FAILED)

        finally:
            try:
                if self.state != ExecutionState.IDLE:
                    self._change_state(ExecutionState.IDLE)
            except Exception as e:
                self.logger.error(f"Failed to reset state to IDLE: {e}")
                self.state = ExecutionState.IDLE

    # ======================================================
    # Atomic Steps (Encapsulated)
    # ======================================================

    def _login(self):
        """The executor loads its own selectors internally."""
        if not self.executor.ensure_login():
            raise LoginFailedError("Login check returned False")

    def _navigate(self, teams: str):
        if not self.executor.navigate_to_match(teams):
            raise NavigationFailedError(f"Could not navigate to match: {teams}")

    def _analyze(self, teams: str, market: str) -> float:
        odds = self.executor.find_odds(teams, market)
        if not odds or odds <= 1.0:
            raise PipelineError(f"Invalid odds found: {odds}")
        return odds

    def _place(self, teams: str, market: str, stake: float):
        if not self.executor.place_bet(teams, market, stake):
            raise PlacementFailedError("Executor failed to interact for placement")

    def _verify(self, teams: str):
        if not self.executor.verify_bet_success(teams):
            self.bus.emit(AppEvent.BET_UNKNOWN, "Placed but not confirmed")
            raise VerificationFailedError("Verification failed")

    # ======================================================
    # Infrastructure
    # ======================================================

    def _execute_step_with_retry(self, state: ExecutionState, func, *args):
        """Generic retry logic wrapper."""
        self._change_state(state)

        last_error = None
        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                func(*args)
                return  # Success
            except Exception as e:
                last_error = e
                self.logger.warning(f"Step {state.name} failed (Attempt {attempt}): {e}")

            if attempt < self.MAX_RETRIES:
                self._change_state(ExecutionState.RETRY_WAIT)
                time.sleep(self.RETRY_DELAY)
                self._change_state(state)

        # Propagate the last exception after retries exhausted
        if last_error:
            raise last_error

    def _change_state(self, new_state: ExecutionState):
        self.state = new_state
        self.bus.emit(AppEvent.STATE_CHANGE, {"state": new_state.name})

    def _handle_failure(self, reason: str):
        self.logger.error(f"Pipeline Terminated: {reason}")
        self._change_state(ExecutionState.FAILED)
        self.bus.emit(AppEvent.BET_FAILED, {"reason": reason})
