"""
SuperAgentController — Central orchestrator for SuperAgent V3.

Single point of coordination between:
  - StateManager (state machine)
  - DomExecutorPlaywright (browser)
  - AITrainerEngine (AI decisions)
  - HealthMonitor (immortality)
  - UI (dumb display layer)

The UI only talks to the Controller. The Controller talks to everything else.
"""
import time
import threading
from typing import Optional

from core.state_machine import AgentState, StateManager


class SuperAgentController:
    """Central orchestrator — the brain of SuperAgent V3.

    Usage (from main.py):
        controller = SuperAgentController(logger, config)
        controller.set_executor(executor)
        controller.set_trainer(trainer)
        controller.set_monitor(monitor)
        controller.boot()

    Usage (from UI):
        controller.handle_signal(signal_data)
        controller.ask_trainer("question")
        state = controller.get_state()
    """

    def __init__(self, logger, config: dict = None):
        self.logger = logger
        self.config = config or {}

        # Core components (injected after init)
        self.executor = None
        self.trainer = None
        self.monitor = None
        self.vision = None
        self.telegram_learner = None
        self.rpa_healer = None

        # State machine
        self.state_manager = StateManager(logger, initial_state=AgentState.BOOT)

        # Signal processing
        self._signal_lock = threading.Lock()
        self._signal_count = 0
        self._bet_results: list = []

    # ------------------------------------------------------------------
    #  Dependency injection
    # ------------------------------------------------------------------
    def set_executor(self, executor):
        self.executor = executor
        self.logger.info("[Controller] Executor connected")

    def set_trainer(self, trainer):
        self.trainer = trainer
        self.logger.info("[Controller] AITrainer connected")

    def set_monitor(self, monitor):
        self.monitor = monitor
        self.logger.info("[Controller] HealthMonitor connected")

    def set_vision(self, vision):
        self.vision = vision

    def set_telegram_learner(self, telegram_learner):
        self.telegram_learner = telegram_learner

    def set_rpa_healer(self, rpa_healer):
        self.rpa_healer = rpa_healer

    # ------------------------------------------------------------------
    #  Boot sequence
    # ------------------------------------------------------------------
    def boot(self):
        """V3 boot sequence — transition from BOOT to IDLE."""
        self.logger.info("[Controller] V3 Boot sequence starting...")
        self.state_manager.transition(AgentState.IDLE)
        self.logger.info("[Controller] V3 Boot complete — state: IDLE")

    # ------------------------------------------------------------------
    #  Signal handling (from Telegram → UI → Controller)
    # ------------------------------------------------------------------
    def handle_signal(self, signal_data: dict) -> bool:
        """Process a Telegram signal end-to-end.
        Returns True if bet was placed successfully."""
        with self._signal_lock:
            self._signal_count += 1
            sig_num = self._signal_count

        teams = signal_data.get("teams", "")
        market = signal_data.get("market", "")
        self.logger.info(f"[Controller] Signal #{sig_num}: {teams} / {market}")

        if not self.executor:
            self.logger.error("[Controller] No executor available")
            return False

        # Heartbeat
        if self.monitor:
            self.monitor.heartbeat()

        # State: NAVIGATING
        if not self.state_manager.transition(AgentState.NAVIGATING):
            self.logger.warning("[Controller] Cannot transition to NAVIGATING")
            return False

        try:
            selectors = self.executor._load_selectors()

            # Login
            if not self.executor.ensure_login(selectors):
                self.state_manager.transition(AgentState.ERROR)
                self.logger.error("[Controller] Login failed")
                self.state_manager.transition(AgentState.IDLE)
                return False

            # Navigate
            if teams and not self.executor.navigate_to_match(teams, selectors):
                self.state_manager.transition(AgentState.ERROR)
                self.logger.error(f"[Controller] Match not found: {teams}")
                self.state_manager.transition(AgentState.IDLE)
                return False

            # Select market
            if market and not self.executor.select_market(market, selectors):
                self.state_manager.transition(AgentState.ERROR)
                self.logger.error(f"[Controller] Market not found: {market}")
                self.state_manager.transition(AgentState.IDLE)
                return False

            # State: BETTING
            self.state_manager.transition(AgentState.BETTING)
            result = self.executor.place_bet(selectors)

            # Record result
            self._bet_results.append({
                "teams": teams,
                "market": market,
                "placed": result,
                "timestamp": time.time(),
            })

            self.state_manager.transition(AgentState.IDLE)
            return result

        except Exception as e:
            self.logger.error(f"[Controller] Signal processing error: {e}")
            self.state_manager.transition(AgentState.ERROR)
            # Try to recover
            if self.executor:
                try:
                    self.state_manager.transition(AgentState.RECOVERING)
                    self.executor.recover_session()
                except Exception:
                    pass
            self.state_manager.transition(AgentState.IDLE)
            return False

    # ------------------------------------------------------------------
    #  AI Trainer interface (from UI)
    # ------------------------------------------------------------------
    def ask_trainer(self, question: str,
                    include_dom: bool = False,
                    include_screenshot: bool = False) -> str:
        """Ask the AI trainer a question with optional context."""
        if not self.trainer:
            return "AI Trainer non disponibile."

        dom = None
        screenshot = None

        if include_dom and self.executor:
            try:
                dom = self.executor.get_dom_snapshot()
            except Exception as e:
                self.logger.warning(f"[Controller] DOM snapshot failed: {e}")

        if include_screenshot and self.executor:
            try:
                screenshot = self.executor.take_screenshot_b64()
            except Exception as e:
                self.logger.warning(f"[Controller] Screenshot failed: {e}")

        prev = self.state_manager.state
        self.state_manager.transition(AgentState.ANALYZING)
        try:
            result = self.trainer.ask(question, dom_snapshot=dom, screenshot_b64=screenshot)
            return result
        finally:
            self.state_manager.force_state(prev)

    def clear_trainer_memory(self):
        """Clear the AI trainer conversation memory."""
        if self.trainer:
            self.trainer.clear_memory()

    # ------------------------------------------------------------------
    #  Status / Stats (for UI)
    # ------------------------------------------------------------------
    def get_state(self) -> str:
        """Return current state name."""
        return self.state_manager.state.name

    def get_stats(self) -> dict:
        """Return operational statistics."""
        total = len(self._bet_results)
        placed = sum(1 for r in self._bet_results if r.get("placed"))
        return {
            "state": self.get_state(),
            "signals_received": self._signal_count,
            "bets_total": total,
            "bets_placed": placed,
            "bets_failed": total - placed,
            "uptime_s": time.time() - self.monitor.start_time.timestamp() if self.monitor else 0,
        }

    def get_state_history(self, n: int = 20) -> list:
        """Return last N state transitions."""
        return self.state_manager.get_history(n)

    # ------------------------------------------------------------------
    #  Stealth mode management
    # ------------------------------------------------------------------
    def set_stealth_mode(self, mode: str):
        """Set stealth mode on executor: 'slow', 'balanced', 'pro'."""
        if self.executor and hasattr(self.executor, 'stealth_mode'):
            self.executor.stealth_mode = mode
            self.logger.info(f"[Controller] Stealth mode set to: {mode}")

    def get_stealth_mode(self) -> str:
        """Get current stealth mode."""
        if self.executor and hasattr(self.executor, 'stealth_mode'):
            return self.executor.stealth_mode
        return "balanced"

    # ------------------------------------------------------------------
    #  Shutdown
    # ------------------------------------------------------------------
    def shutdown(self):
        """Graceful shutdown."""
        self.logger.info("[Controller] Shutdown initiated")
        self.state_manager.force_state(AgentState.SHUTDOWN)
        if self.executor:
            try:
                self.executor.close()
            except Exception:
                pass
