"""
State Machine — Thread-safe agent state management for SuperAgent V3.

AgentState enum defines all possible operational states.
StateManager provides atomic transitions with Lock protection.
"""
import threading
from enum import Enum, auto
from typing import Optional, Callable, List


class AgentState(Enum):
    """All possible states the SuperAgent can be in."""
    BOOT = auto()
    IDLE = auto()
    LISTENING = auto()
    ANALYZING = auto()
    NAVIGATING = auto()
    BETTING = auto()
    RECOVERING = auto()
    MAINTENANCE = auto()
    ERROR = auto()
    SHUTDOWN = auto()


# Valid transitions: {from_state: [allowed_to_states]}
VALID_TRANSITIONS = {
    AgentState.BOOT:        [AgentState.IDLE, AgentState.ERROR, AgentState.SHUTDOWN],
    AgentState.IDLE:        [AgentState.LISTENING, AgentState.ANALYZING, AgentState.NAVIGATING,
                             AgentState.MAINTENANCE, AgentState.ERROR, AgentState.SHUTDOWN],
    AgentState.LISTENING:   [AgentState.IDLE, AgentState.ANALYZING, AgentState.ERROR,
                             AgentState.SHUTDOWN],
    AgentState.ANALYZING:   [AgentState.NAVIGATING, AgentState.IDLE, AgentState.ERROR,
                             AgentState.SHUTDOWN],
    AgentState.NAVIGATING:  [AgentState.BETTING, AgentState.IDLE, AgentState.ERROR,
                             AgentState.RECOVERING, AgentState.SHUTDOWN],
    AgentState.BETTING:     [AgentState.IDLE, AgentState.ERROR, AgentState.RECOVERING,
                             AgentState.SHUTDOWN],
    AgentState.RECOVERING:  [AgentState.IDLE, AgentState.ERROR, AgentState.SHUTDOWN],
    AgentState.MAINTENANCE: [AgentState.BOOT, AgentState.SHUTDOWN],
    AgentState.ERROR:       [AgentState.IDLE, AgentState.RECOVERING, AgentState.SHUTDOWN,
                             AgentState.BOOT],
    AgentState.SHUTDOWN:    [],  # terminal state
}


class StateManager:
    """Thread-safe state machine with transition validation and callbacks.

    Usage:
        sm = StateManager(logger)
        sm.on_enter(AgentState.BETTING, my_callback)
        sm.transition(AgentState.IDLE)
    """

    def __init__(self, logger, initial_state: AgentState = AgentState.BOOT):
        self.logger = logger
        self._state = initial_state
        self._lock = threading.Lock()
        self._on_enter_callbacks: dict[AgentState, List[Callable]] = {}
        self._on_exit_callbacks: dict[AgentState, List[Callable]] = {}
        self._history: list[tuple] = []  # (timestamp, from_state, to_state)

    @property
    def state(self) -> AgentState:
        with self._lock:
            return self._state

    def on_enter(self, state: AgentState, callback: Callable):
        """Register a callback to fire when entering a state."""
        self._on_enter_callbacks.setdefault(state, []).append(callback)

    def on_exit(self, state: AgentState, callback: Callable):
        """Register a callback to fire when leaving a state."""
        self._on_exit_callbacks.setdefault(state, []).append(callback)

    def transition(self, new_state: AgentState) -> bool:
        """Attempt a state transition. Returns True on success."""
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
            import time
            self._history.append((time.time(), old, new_state))
            # Trim history to last 100 entries
            if len(self._history) > 100:
                self._history = self._history[-100:]

            self.logger.info(f"[StateMachine] {old.name} -> {new_state.name}")

        # Fire enter callbacks (outside lock to avoid deadlocks)
        for cb in self._on_enter_callbacks.get(new_state, []):
            try:
                cb()
            except Exception as e:
                self.logger.error(f"[StateMachine] on_enter callback error: {e}")

        return True

    def is_state(self, *states: AgentState) -> bool:
        """Check if current state is one of the given states."""
        with self._lock:
            return self._state in states

    def get_history(self, last_n: int = 20) -> list:
        """Return the last N state transitions."""
        with self._lock:
            return list(self._history[-last_n:])

    def force_state(self, state: AgentState):
        """Force a state without validation (emergency use only)."""
        with self._lock:
            old = self._state
            self._state = state
            self.logger.warning(f"[StateMachine] FORCED: {old.name} -> {state.name}")
