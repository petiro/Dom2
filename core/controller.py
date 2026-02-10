"""
SuperAgentController V4 — Central orchestrator with Qt Signals and thread safety.

Single point of coordination between:
  - StateManager (state machine with Qt Signal)
  - DomExecutorPlaywright (browser)
  - AITrainerEngine (AI decisions)
  - HealthMonitor (immortality)
  - SystemWatchdog (lifecycle)
  - UI (dumb display layer)

V4 enhancements:
  - QObject with log_message/training_complete Signals
  - _stop_event for graceful shutdown (no zombie threads)
  - _boot_lock to prevent concurrent boots
  - _executor_lock for thread-safe browser access
  - CDP watchdog for browser health
  - request_training() Slot for async training
  - Race condition fix (don't reset IDLE during shutdown)
"""
import time
import threading
from typing import Optional

from PySide6.QtCore import QObject, Signal, Slot

from core.state_machine import AgentState, StateManager
from core.signal_parser import TelegramSignalParser
from core.money_management import RoserpinaTable
from core.bet_worker import BetWorker
from core.security import Vault


class SuperAgentController(QObject):
    """Central orchestrator — the brain of SuperAgent V4.

    Emits:
      - log_message(str): for UI log display
      - training_complete(str): when AI training finishes

    Usage (from main.py):
        controller = SuperAgentController(logger, config)
        controller.set_executor(executor)
        controller.set_trainer(trainer)
        controller.set_monitor(monitor)
        controller.start_system()

    Usage (from UI):
        controller.handle_signal(signal_data)
        controller.request_training()
        state = controller.get_state()
    """

    # Qt Signals for UI binding
    log_message = Signal(str)
    training_complete = Signal(str)
    mapping_ready = Signal(str)

    def __init__(self, logger, config: dict = None):
        super().__init__()
        self.logger = logger
        self.config = config or {}

        # Core components (injected after init)
        self.executor = None
        self.trainer = None
        self.monitor = None
        self.vision = None
        self.telegram_learner = None
        self.rpa_healer = None
        self.watchdog = None  # SystemWatchdog (lifecycle)
        self.command_parser = None  # CommandParser (signal → steps)
        self._os_human = None  # HumanOS for desktop recovery

        # State machine
        self.state_manager = StateManager(logger, initial_state=AgentState.BOOT)

        # V4: Thread safety primitives
        self._stop_event = threading.Event()
        self._boot_lock = threading.Lock()
        self._executor_lock = threading.RLock()

        # Signal processing
        self._signal_lock = threading.Lock()
        self._signal_count = 0
        self._bet_results: list = []

        # Roserpina / Blind Over
        self.parser = TelegramSignalParser()
        self.table = RoserpinaTable(table_id=1)  # Default Table 1
        self.bet_worker = None

        # Secure credential vault
        self.vault = Vault()
        self.current_config = self.vault.decrypt_data()
        self.telegram_worker = None

    # ------------------------------------------------------------------
    #  Internal logging (emits Qt Signal + logger)
    # ------------------------------------------------------------------
    def _log(self, msg: str):
        self.logger.info(msg)
        self.safe_emit(self.log_message, msg)

    def safe_emit(self, signal, *args):
        """Emit a Qt signal, ignoring RuntimeError if UI is already destroyed."""
        try:
            signal.emit(*args)
        except RuntimeError:
            pass

    # ------------------------------------------------------------------
    #  Dependency injection
    # ------------------------------------------------------------------
    def set_executor(self, executor):
        self.executor = executor
        self._log("[Controller] Executor connected")

    def set_trainer(self, trainer):
        self.trainer = trainer
        # V4: also connect trainer to executor
        if trainer and self.executor:
            trainer.set_executor(self.executor)
        self._log("[Controller] AITrainer connected")

    def set_monitor(self, monitor):
        self.monitor = monitor
        self._log("[Controller] HealthMonitor connected")

    def set_vision(self, vision):
        self.vision = vision

    def set_telegram_learner(self, telegram_learner):
        self.telegram_learner = telegram_learner

    def set_rpa_healer(self, rpa_healer):
        self.rpa_healer = rpa_healer

    def set_command_parser(self, parser):
        """Connect CommandParser for Telegram signal → TaskStep conversion."""
        self.command_parser = parser
        self._log("[Controller] CommandParser connected")

    def set_watchdog(self, watchdog):
        """Connect SystemWatchdog and wire its signals to Controller recovery."""
        self.watchdog = watchdog
        if watchdog:
            watchdog.browser_died.connect(self.on_browser_died)
            watchdog.resource_warning.connect(self._on_resource_warning)
            if hasattr(watchdog, 'request_recycle'):
                watchdog.request_recycle.connect(self._handle_recycle_request)
            self._log("[Controller] SystemWatchdog connected")

    def _handle_recycle_request(self):
        with self._executor_lock:
            if self.executor:
                self.executor.recycle_browser()
                self.executor.launch_browser_cdp()

    def _init_os_human(self):
        """Lazy-init HumanOS for desktop-level recovery."""
        if self._os_human is None:
            try:
                from core.os_human_interaction import HumanOS
                self._os_human = HumanOS(self.logger)
                self._log("[Controller] HumanOS initialized for desktop recovery")
            except Exception as e:
                self.logger.warning(f"[Controller] HumanOS not available: {e}")

    # ------------------------------------------------------------------
    #  Boot sequence (V4: with boot lock + async option)
    # ------------------------------------------------------------------
    def boot(self):
        """V4 boot sequence — transition from BOOT to IDLE.
        Backward-compatible synchronous boot."""
        with self._boot_lock:
            self._log("[Controller] V4 Boot sequence starting...")
            self.state_manager.transition(AgentState.IDLE)
            self._log("[Controller] V4 Boot complete — state: IDLE")

    def start_system(self):
        """V4 async boot — call after UI is visible.
        Runs boot in background thread so UI doesn't freeze."""
        def _async_boot():
            with self._boot_lock:
                if self._stop_event.is_set():
                    return
                self._log("[Controller] V4 async boot starting...")
                self.state_manager.transition(AgentState.IDLE)
                self._log("[Controller] V4 async boot complete — state: IDLE")
                # Start CDP watchdog if configured
                if self.config.get("rpa", {}).get("cdp_watchdog", False):
                    self.start_cdp_watchdog()

        t = threading.Thread(target=_async_boot, name="controller-boot", daemon=True)
        t.start()

    # ------------------------------------------------------------------
    #  CDP Watchdog (V4: browser health monitoring)
    # ------------------------------------------------------------------
    def start_cdp_watchdog(self, interval: int = 60):
        """Start a daemon thread that periodically checks browser health.
        If browser dies, emits signal and attempts recovery."""
        def _watchdog():
            while not self._stop_event.is_set():
                self._stop_event.wait(interval)
                if self._stop_event.is_set():
                    break
                with self._executor_lock:
                    if self.executor and not self.executor.check_health():
                        self._log("[Controller] CDP Watchdog: browser dead — recovering")
                        self.state_manager.set_state(AgentState.RECOVERING)
                        try:
                            self.executor.recover_session()
                            if not self._stop_event.is_set():
                                self.state_manager.set_state(AgentState.IDLE)
                            self._log("[Controller] CDP Watchdog: recovery successful")
                        except Exception as e:
                            self._log(f"[Controller] CDP Watchdog: recovery failed: {e}")
                            self.state_manager.set_state(AgentState.ERROR)

        t = threading.Thread(target=_watchdog, name="cdp-watchdog", daemon=True)
        t.start()
        self._log("[Controller] CDP Watchdog started")

    # ------------------------------------------------------------------
    #  Watchdog Slots (V4: browser death recovery)
    # ------------------------------------------------------------------
    @Slot()
    def on_browser_died(self):
        """Called when SystemWatchdog detects Chrome is dead.
        Triggers full recovery: close executor → HumanOS reopen → CDP reconnect."""
        if self._stop_event.is_set():
            return
        self._log("[Controller] Browser death detected by Watchdog — starting recovery")
        self.state_manager.set_state(AgentState.RECOVERING)

        def _recover():
            try:
                with self._executor_lock:
                    # 1. Close any dead executor state
                    if self.executor:
                        try:
                            self.executor.close()
                        except Exception as close_e:
                            self.logger.warning(f"[Controller] Error closing dead executor (expected during recovery): {close_e}")

                    # 2. Try HumanOS desktop relaunch (Win+D → find icon → doubleClick)
                    self._init_os_human()
                    if self._os_human and self._os_human.available:
                        self._log("[Controller] Reopening Chrome via HumanOS desktop...")
                        opened = self._os_human.open_browser_from_desktop()
                        if opened:
                            self._log("[Controller] Chrome reopened — connecting via CDP...")
                            time.sleep(5)

                            CDP_RECONNECT_ATTEMPTS = 10
                            CDP_RECONNECT_INTERVAL = 1

                            success = False

                            if self.executor:
                                for _ in range(CDP_RECONNECT_ATTEMPTS):

                                    if self._stop_event.is_set():
                                        break

                                    if self.executor.launch_browser_cdp():
                                        success = True
                                        break

                                    time.sleep(CDP_RECONNECT_INTERVAL)
                                if success:
                                    self._log("[Controller] CDP reconnect successful!")
                                    if not self._stop_event.is_set():
                                        self.state_manager.set_state(AgentState.IDLE)
                                    return
                                else:
                                    self._log("[Controller] CDP reconnect failed")

                    # 3. Fallback: standard executor recovery (persistent context)
                    self._log("[Controller] Falling back to standard session recovery...")
                    if self.executor:
                        self.executor.recover_session()
                        if not self._stop_event.is_set():
                            self.state_manager.set_state(AgentState.IDLE)
                        self._log("[Controller] Standard recovery successful")

            except Exception as e:
                self._log(f"[Controller] Full recovery failed: {e}")
                self.state_manager.set_state(AgentState.ERROR)

        t = threading.Thread(target=_recover, name="browser-recovery", daemon=True)
        t.start()

    @Slot(str)
    def _on_resource_warning(self, msg: str):
        """Handle resource warnings from SystemWatchdog."""
        self._log(f"[Watchdog] {msg}")
        # If executor supports check_and_recycle, trigger it
        if self.executor and hasattr(self.executor, 'check_and_recycle'):
            try:
                with self._executor_lock:
                    self.executor.check_and_recycle()
            except Exception as e:
                self.logger.warning(f"[Controller] Memory check triggered by warning failed: {e}")

    # ------------------------------------------------------------------
    #  V4: Step-based execution (CommandParser pipeline)
    # ------------------------------------------------------------------
    def handle_signal_v4(self, signal_data: dict) -> bool:
        """V4 signal handler: signal → CommandParser → TaskSteps → execute.
        Falls back to legacy handle_signal if CommandParser not available."""
        if not self.command_parser:
            return self.handle_signal(signal_data)

        steps = self.command_parser.parse(signal_data)
        if not steps:
            self._log("[Controller] CommandParser returned no steps — skipping")
            return False

        return self.execute_steps(steps)

    def execute_steps(self, steps) -> bool:
        """Execute an ordered list of TaskStep objects against the executor.
        Returns True if all steps completed successfully."""
        if self._stop_event.is_set() or not self.executor:
            return False

        if not self.state_manager.transition(AgentState.NAVIGATING):
            self._log("[Controller] Cannot transition to NAVIGATING for step execution")
            return False

        if self.monitor:
            self.monitor.heartbeat()

        try:
            with self._executor_lock:
                selectors = self.executor._load_selectors()

                for step in steps:
                    self._log(f"[Controller] Step: {step.description or step.action}")
                    success = False
                    last_err = None

                    for attempt in range(step.retries + 1):
                        try:
                            success = self._execute_single_step(step, selectors)
                            if success:
                                break
                        except Exception as e:
                            last_err = e
                            self._log(f"[Controller] Step {step.action} attempt {attempt+1} failed: {e}")
                            # Try AI healing if enabled
                            if step.heal_on_fail and self.rpa_healer and attempt < step.retries:
                                self._log("[Controller] Attempting AI selector healing...")
                                self.state_manager.set_state(AgentState.HEALING)
                                try:
                                    self.rpa_healer.heal()
                                    selectors = self.executor._load_selectors()
                                except Exception as heal_e:
                                    self.logger.warning(f"[Controller] AI healing attempt failed: {heal_e}")
                                self.state_manager.set_state(AgentState.NAVIGATING)

                    if not success:
                        self._log(f"[Controller] Step {step.action} failed after {step.retries+1} attempts: {last_err}")
                        if not self._stop_event.is_set():
                            self.state_manager.set_state(AgentState.IDLE)
                        return False

            if not self._stop_event.is_set():
                self.state_manager.set_state(AgentState.IDLE)
            return True

        except Exception as e:
            self._log(f"[Controller] Step execution error: {e}")
            self.state_manager.set_state(AgentState.ERROR)
            if not self._stop_event.is_set():
                self.state_manager.set_state(AgentState.IDLE)
            return False

    def _execute_single_step(self, step, selectors) -> bool:
        """Execute one TaskStep. Returns True on success."""
        action = step.action
        params = step.params

        if action == "login":
            return self.executor.ensure_login(selectors)
        elif action == "navigate":
            return self.executor.navigate_to_match(params.get("teams", ""), selectors)
        elif action == "select_market":
            self.state_manager.set_state(AgentState.NAVIGATING)
            return self.executor.select_market(params.get("market", ""), selectors)
        elif action == "place_bet":
            self.state_manager.set_state(AgentState.BETTING)
            return self.executor.place_bet(selectors)
        else:
            self._log(f"[Controller] Unknown step action: {action}")
            return False

    # ------------------------------------------------------------------
    #  Signal handling (from Telegram → UI → Controller) [legacy]
    # ------------------------------------------------------------------
    def handle_signal(self, signal_data: dict) -> bool:
        """Process a Telegram signal end-to-end.
        Returns True if bet was placed successfully."""
        if self._stop_event.is_set():
            return False

        with self._signal_lock:
            self._signal_count += 1
            sig_num = self._signal_count

        teams = signal_data.get("teams", "")
        market = signal_data.get("market", "")
        self._log(f"[Controller] Signal #{sig_num}: {teams} / {market}")

        if not self.executor:
            self._log("[Controller] No executor available")
            return False

        # Heartbeat
        if self.monitor:
            self.monitor.heartbeat()

        # State: NAVIGATING
        if not self.state_manager.transition(AgentState.NAVIGATING):
            self._log("[Controller] Cannot transition to NAVIGATING")
            return False

        try:
            with self._executor_lock:
                selectors = self.executor._load_selectors()

                # Login
                if not self.executor.ensure_login(selectors):
                    self.state_manager.transition(AgentState.ERROR)
                    self._log("[Controller] Login failed")
                    self.state_manager.transition(AgentState.IDLE)
                    return False

                # Navigate
                if teams and not self.executor.navigate_to_match(teams, selectors):
                    self.state_manager.transition(AgentState.ERROR)
                    self._log(f"[Controller] Match not found: {teams}")
                    self.state_manager.transition(AgentState.IDLE)
                    return False

                # Select market
                if market and not self.executor.select_market(market, selectors):
                    self.state_manager.transition(AgentState.ERROR)
                    self._log(f"[Controller] Market not found: {market}")
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

            # V4: Race condition guard — don't reset if shutting down
            if not self._stop_event.is_set():
                self.state_manager.transition(AgentState.IDLE)
            return result

        except Exception as e:
            self._log(f"[Controller] Signal processing error: {e}")
            self.state_manager.transition(AgentState.ERROR)
            # Try to recover
            if self.executor:
                try:
                    self.state_manager.transition(AgentState.RECOVERING)
                    with self._executor_lock:
                        self.executor.recover_session()
                except Exception as e:
                    self._log(f"[Controller] Recovery during signal processing failed: {e}")
            if not self._stop_event.is_set():
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
                with self._executor_lock:
                    dom = self.executor.get_dom_snapshot()
            except Exception as e:
                self.logger.warning(f"[Controller] DOM snapshot failed: {e}")

        if include_screenshot and self.executor:
            try:
                with self._executor_lock:
                    screenshot = self.executor.take_screenshot_b64()
            except Exception as e:
                self.logger.warning(f"[Controller] Screenshot failed: {e}")

        prev = self.state_manager.state
        self.state_manager.transition(AgentState.ANALYZING)
        try:
            result = self.trainer.ask(question, dom_snapshot=dom, screenshot_b64=screenshot)
            return result
        finally:
            if not self._stop_event.is_set():
                self.state_manager.force_state(prev)

    # ------------------------------------------------------------------
    #  V4: Async Training (Slot for UI button)
    # ------------------------------------------------------------------
    @Slot()
    def request_training(self):
        """Run a full training step in a background thread.
        Emits training_complete Signal when done."""
        if not self.trainer:
            self.safe_emit(self.training_complete, "Trainer non disponibile.")
            return

        def _train():
            self.state_manager.set_state(AgentState.TRAINING)
            self._log("[Controller] Training started...")
            try:
                result = self.trainer.train_step()
                self._log(f"[Controller] Training completed — {len(result)} chars")
                self.safe_emit(self.training_complete, result)
            except Exception as e:
                self._log(f"[Controller] Training error: {e}")
                self.safe_emit(self.training_complete, f"Errore training: {e}")
            finally:
                # V4: Race condition guard
                if not self._stop_event.is_set():
                    self.state_manager.set_state(AgentState.IDLE)

        t = threading.Thread(target=_train, name="training-thread", daemon=True)
        t.start()

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
            self._log(f"[Controller] Stealth mode set to: {mode}")

    def get_stealth_mode(self) -> str:
        """Get current stealth mode."""
        if self.executor and hasattr(self.executor, 'stealth_mode'):
            return self.executor.stealth_mode
        return "balanced"

    # ------------------------------------------------------------------
    #  Auto-Mapping (AI selector generation)
    # ------------------------------------------------------------------
    def request_auto_mapping(self, url):
        """Start AI auto-mapping for the given URL."""
        api_key = self.vault.decrypt_data().get("openrouter_api_key")

        if not api_key:
            self.safe_emit(self.log_message, "API Key mancante")
            return

        with self._executor_lock:
            # Navigate if needed and extract DOM
            if self.executor and self.executor.page:
                if self.executor.page.url != url:
                    self.executor.go_to_url(url)
                dom_data = self.executor.get_dom_snapshot()
            else:
                self.safe_emit(self.log_message, "Browser non inizializzato")
                return

            from core.auto_mapper_worker import AutoMapperWorker
            from PySide6.QtCore import QThread
            self.mapper_worker = AutoMapperWorker(api_key, dom_data)
            self._mapper_thread = QThread()
            self.mapper_worker.moveToThread(self._mapper_thread)
            self._mapper_thread.started.connect(self.mapper_worker.run)
            self.mapper_worker.finished.connect(self.on_mapping_success)
            self.mapper_worker.error.connect(lambda e: self.safe_emit(self.log_message, e))
            self.mapper_worker.finished.connect(self._mapper_thread.quit)
            self.mapper_worker.error.connect(self._mapper_thread.quit)
            self._mapper_thread.start()

    def on_mapping_success(self, result_dict):
        import yaml
        yaml_code = yaml.dump(result_dict, default_flow_style=False)
        self.safe_emit(self.mapping_ready, yaml_code)

    def test_mapping_visual(self, yaml_code):
        with self._executor_lock:
            if self.executor:
                self.executor.highlight_selectors(yaml_code)

    def save_selectors_yaml(self, yaml_code):
        try:
            with open("config/selectors.yaml", "w", encoding="utf-8") as f:
                f.write(yaml_code)
            self.safe_emit(self.log_message, "selectors.yaml salvato correttamente")
        except Exception as e:
            self.safe_emit(self.log_message, f"Errore salvataggio YAML: {e}")

    # ------------------------------------------------------------------
    #  Telegram Secure Connection
    # ------------------------------------------------------------------
    def connect_telegram(self, config):
        """Save credentials to vault and (re)start Telegram worker."""
        self.vault.encrypt_data(config)
        self.current_config = config

        if self.telegram_worker:
            self.telegram_worker.stop()

        from core.telegram_worker import TelegramWorker
        self.telegram_worker = TelegramWorker(config)
        self.telegram_worker.message_received.connect(self.handle_telegram_signal)
        self.telegram_worker.start()

    # ------------------------------------------------------------------
    #  Roserpina / Blind Over (Telegram signal → BetWorker)
    # ------------------------------------------------------------------
    def handle_telegram_signal(self, text):
        # 1. Check Pendente
        if self.table.is_pending:
            self.safe_emit(self.log_message, "⚠️ Scommessa in corso, segnale ignorato.")
            return

        # 2. Parsing
        data = self.parser.parse(text)
        if not data['match']:
            return

        # 3. Avvio Thread Scommessa (is_pending gestito da BetWorker.run)
        self.bet_worker = BetWorker(self.table, self.executor, data)

        self.bet_worker.finished.connect(self.on_bet_complete)
        self.bet_worker.start()

    def on_bet_complete(self, result):
        self.table.is_pending = False
        if result:
            self.safe_emit(self.log_message, "Bet Piazzata")
        else:
            self.safe_emit(self.log_message, "Errore Bet")

    # ------------------------------------------------------------------
    #  Shutdown (V4: graceful with _stop_event)
    # ------------------------------------------------------------------
    def shutdown(self):
        """Graceful shutdown — signals all daemon threads to stop."""
        self._log("[Controller] Shutdown initiated")
        self._stop_event.set()
        self.state_manager.force_state(AgentState.SHUTDOWN)
        with self._executor_lock:
            if self.executor:
                try:
                    self.executor.close()
                except Exception as recovery_exc:
                    self.logger.error(f"[Controller] Session recovery failed: {recovery_exc}")
