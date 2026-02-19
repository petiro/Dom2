import time
import threading
from enum import Enum, auto
from typing import Callable, List

# 🔴 FIX PYSIDE6 IN GITHUB ACTIONS
try:
    from PySide6.QtCore import QObject, Signal
except ImportError:
    class QObject: pass
    class Signal:
        def __init__(self, *args, **kwargs): pass
        def emit(self, *args, **kwargs): pass

class AgentState(Enum):
    BOOT = auto()
    IDLE = auto()
    INITIALIZING = auto()
    LISTENING = auto()
    ANALYZING = auto()
    SCOUTING = auto()
    NAVIGATING = auto()
    BETTING = auto()
    HEALING = auto()
    RECOVERING = auto()
    MAINTENANCE = auto()
    TRAINING = auto()
    ERROR = auto()
    SHUTDOWN = auto()

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
    AgentState.MAINTENANCE:  [AgentState.BOOT, AgentState.IDLE, AgentState.SHUTDOWN],
    AgentState.TRAINING:     [AgentState.IDLE, AgentState.ERROR, AgentState.SHUTDOWN],
    AgentState.ERROR:        [AgentState.IDLE, AgentState.RECOVERING, AgentState.HEALING,
                              AgentState.SHUTDOWN, AgentState.BOOT],
    AgentState.SHUTDOWN:     [],
}

class StateManager(QObject):
    state_changed = Signal(object)

    def __init__(self, logger, initial_state: AgentState = AgentState.BOOT):
        super().__init__()
        self.logger = logger
        self._state = initial_state
        self._lock = threading.RLock()
        self._on_enter_callbacks: dict[AgentState, List[Callable]] = {}
        self._on_exit_callbacks: dict[AgentState, List[Callable]] = {}
        self._history: list[tuple] = []

    @property
    def state(self) -> AgentState:
        with self._lock:
            return self._state

    @property
    def current(self) -> AgentState:
        return self.state

    def is_idle(self) -> bool:
        with self._lock:
            return self._state == AgentState.IDLE

    def is_state(self, *states: AgentState) -> bool:
        with self._lock:
            return self._state in states

    def on_enter(self, state: AgentState, callback: Callable):
        self._on_enter_callbacks.setdefault(state, []).append(callback)

    def on_exit(self, state: AgentState, callback: Callable):
        self._on_exit_callbacks.setdefault(state, []).append(callback)

    def transition(self, new_state: AgentState) -> bool:
        with self._lock:
            old = self._state
            allowed = VALID_TRANSITIONS.get(old, [])
            if new_state not in allowed:
                self.logger.warning("[StateMachine] Invalid transition: %s -> %s", old.name, new_state.name)
                return False

            for cb in self._on_exit_callbacks.get(old, []):
                try:
                    cb()
                except Exception as e:
                    self.logger.error("[StateMachine] on_exit callback error (%s): %s", cb, e)

            self._state = new_state
            self._history.append((time.time(), old, new_state))
            if len(self._history) > 100:
                self._history = self._history[-100:]

            self.logger.info("[StateMachine] %s -> %s", old.name, new_state.name)

        for cb in self._on_enter_callbacks.get(new_state, []):
            try:
                cb()
            except Exception as e:
                self.logger.error("[StateMachine] on_enter callback error (%s): %s", cb, e)

        self.state_changed.emit(new_state)
        return True

    def set_state(self, new_state: AgentState):
        if not self.transition(new_state):
            self.force_state(new_state)

    def force_state(self, state: AgentState):
        with self._lock:
            old = self._state
            self._state = state
            self.logger.warning("[StateMachine] FORCED: %s -> %s", old.name, state.name)
        self.state_changed.emit(state)

    def get_history(self, last_n: int = 20) -> list:
        with self._lock:
            return list(self._history[-last_n:])