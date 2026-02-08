"""
State Machine V4 — Thread-safe agent state management with Qt Signal support.

AgentState enum defines all operational states.
StateManager uses RLock (reentrant) + emits Qt Signal on state change.
"""
import time
import threading
from enum import Enum, auto
from typing import Callable, List

from PySide6.QtCore import QObject, Signal


class AgentState(Enum):
    """All possible states the SuperAgent can be in."""
    BOOT = auto()
    IDLE = auto()
    INITIALIZING = auto()
    LISTENING = auto()
    ANALYZING = auto()
    SCOUTING = auto()       # Passive analysis / curiosity browsing
    NAVIGATING = auto()
    BETTING = auto()
    HEALING = auto()         # Self-repair (AI selector healing)
    RECOVERING = auto()
    MAINTENANCE = auto()
    TRAINING = auto()        # AI learning session
    ERROR = auto()
    SHUTDOWN = auto()


# Valid transitions: {from_state: [allowed_to_states]}
VALID_TRANSITIONS = {
    AgentState.BOOT:         [AgentState.IDLE, AgentState.INITIALIZING, AgentState.ERROR, AgentState.SHUTDOWN],
    AgentState.INITIALIZING: [AgentState.IDLE, AgentState.ERROR, AgentState.SHUTDOWN],
    AgentState.IDLE:         [AgentState.LISTENING, AgentState.ANALYZING, AgentState.SCOUTING,
                              AgentState.NAVIGATING, AgentState.TRAINING, AgentState.HEALING,
                              AgentState.MAINTENANCE, AgentState.ERROR, AgentState.SHUTDOWN],
    AgentState.LISTENING:    [AgentState.IDLE, AgentState.ANALYZING, AgentState.ERROR, AgentState.SHUTDOWN],
    AgentState.ANALYZING:    [AgentState.NAVIGATING, AgentState.IDLE, AgentState.ERROR, AgentState.SHUTDOWN],
    AgentState.SCOUTING:     [AgentState.IDLE, AgentState.ANALYZING, AgentState.ERROR, AgentState.SHUTDOWN],
    AgentState.NAVIGATING:   [AgentState.BETTING, AgentState.IDLE, AgentState.ERROR,
                              AgentState.RECOVERING, AgentState.HEALING, AgentState.SHUTDOWN],
    AgentState.BETTING:      [AgentState.IDLE, AgentState.ERROR, AgentState.RECOVERING,
                              AgentState.HEALING, AgentState.SHUTDOWN],
    AgentState.HEALING:      [AgentState.IDLE, AgentState.NAVIGATING, AgentState.BETTING,
                              AgentState.ERROR, AgentState.SHUTDOWN],
    AgentState.RECOVERING:   [AgentState.IDLE, AgentState.ERROR, AgentState.SHUTDOWN],
    AgentState.MAINTENANCE:  [AgentState.BOOT, AgentState.SHUTDOWN],
    AgentState.TRAINING:     [AgentState.IDLE, AgentState.ERROR, AgentState.SHUTDOWN],
    AgentState.ERROR:        [AgentState.IDLE, AgentState.RECOVERING, AgentState.HEALING,
                              AgentState.SHUTDOWN, AgentState.BOOT],
    AgentState.SHUTDOWN:     [],  # terminal state
}


class StateManager(QObject):
    """Thread-safe state machine with RLock, Qt Signal, transition validation and callbacks.

    V4 enhancements:
      - RLock (reentrant) for nested lock safety
      - state_changed Qt Signal for UI binding
      - HEALING and TRAINING states
      - set_state() convenience alias
    """
    state_changed = Signal(object)  # emits AgentState on transition

    def __init__(self, logger, initial_state: AgentState = AgentState.BOOT):
        super().__init__()
        self.logger = logger
        self._state = initial_state
        self._lock = threading.RLock()  # V4: Reentrant lock for nested safety
        self._on_enter_callbacks: dict[AgentState, List[Callable]] = {}
        self._on_exit_callbacks: dict[AgentState, List[Callable]] = {}
        self._history: list[tuple] = []

    # ------------------------------------------------------------------
    #  Properties
    # ------------------------------------------------------------------
    @property
    def state(self) -> AgentState:
        with self._lock:
            return self._state

    @property
    def current(self) -> AgentState:
        """Alias for state (V4 compat)."""
        return self.state

    def is_idle(self) -> bool:
        with self._lock:
            return self._state == AgentState.IDLE

    def is_state(self, *states: AgentState) -> bool:
        with self._lock:
            return self._state in states

    # ------------------------------------------------------------------
    #  Callbacks
    # ------------------------------------------------------------------
    def on_enter(self, state: AgentState, callback: Callable):
        self._on_enter_callbacks.setdefault(state, []).append(callback)

    def on_exit(self, state: AgentState, callback: Callable):
        self._on_exit_callbacks.setdefault(state, []).append(callback)

    # ------------------------------------------------------------------
    #  State Transitions
    # ------------------------------------------------------------------
    def transition(self, new_state: AgentState) -> bool:
        """Attempt a validated state transition. Returns True on success."""
        with self._lock:
            old = self._state
            allowed = VALID_TRANSITIONS.get(old, [])
            if new_state not in allowed:
                self.logger.warning(
                    f"[StateMachine] Invalid transition: {old.name} -> {new_state.name}")
                return False

            # Fire exit callbacks
            for cb in self._on_exit_callbacks.get(old, []):
                try:
                    cb()
                except Exception as e:
                    self.logger.error(f"[StateMachine] on_exit callback error: {e}")

            self._state = new_state
            self._history.append((time.time(), old, new_state))
            if len(self._history) > 100:
                self._history = self._history[-100:]

            self.logger.info(f"[StateMachine] {old.name} -> {new_state.name}")

        # Fire enter callbacks and Qt signal (outside lock)
        for cb in self._on_enter_callbacks.get(new_state, []):
            try:
                cb()
            except Exception as e:
                self.logger.error(f"[StateMachine] on_enter callback error: {e}")

        self.state_changed.emit(new_state)
        return True

    def set_state(self, new_state: AgentState):
        """Convenience: try transition, fall back to force if invalid.
        Used by V4 controller for guaranteed state changes."""
        if not self.transition(new_state):
            self.force_state(new_state)

    def force_state(self, state: AgentState):
        """Force a state without validation (emergency use only)."""
        with self._lock:
            old = self._state
            self._state = state
            self.logger.warning(f"[StateMachine] FORCED: {old.name} -> {state.name}")
        self.state_changed.emit(state)

    # ------------------------------------------------------------------
    #  History
    # ------------------------------------------------------------------
    def get_history(self, last_n: int = 20) -> list:
        with self._lock:
            return list(self._history[-last_n:])
