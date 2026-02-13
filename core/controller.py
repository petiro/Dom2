"""
SuperAgentController V4 — Central orchestrator with Qt Signals and thread safety.
"""
import time
import threading
import logging  # ✅ LOGGING
from typing import Optional

from PySide6.QtCore import QObject, Signal, Slot

from core.state_machine import AgentState, StateManager
from core.signal_parser import TelegramSignalParser
from core.money_management import RoserpinaTable
from core.bet_worker import BetWorker
from core.security import Vault

# ✅ SETUP LOGGER
logger = logging.getLogger("SuperAgent")

class SuperAgentController(QObject):
    # Qt Signals for UI binding
    log_message = Signal(str)
    training_complete = Signal(str)
    mapping_ready = Signal(str)

    def __init__(self, logger_instance, config: dict = None):
        super().__init__()
        # Usiamo il logger globale, ma teniamo compatibilità se passato da main
        self.logger = logger 
        self.config = config or {}

        logger.info("🧠 Inizializzazione SuperAgentController V4...") # ✅ LOG

        # Core components (injected after init)
        self.executor = None
        self.trainer = None
        self.monitor = None
        self.vision = None
        self.telegram_learner = None
        self.rpa_healer = None
        self.watchdog = None 
        self.command_parser = None 
        self._os_human = None 

        # State machine
        self.state_manager = StateManager(self.logger, initial_state=AgentState.BOOT)

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
        self.table = RoserpinaTable(table_id=1) 
        self.bet_worker = None

        # Secure credential vault
        self.vault = Vault()
        self.current_config = self.vault.decrypt_data()
        self.telegram_worker = None

        # Auto-mapping state
        self.mapper_worker = None
        self._mapper_thread = None

    # ------------------------------------------------------------------
    #  Internal logging (emits Qt Signal + logger)
    # ------------------------------------------------------------------
    def _log(self, msg: str):
        # Scrive sia su disco/console che sulla UI
        logger.info(msg) # ✅ LOG
        self.safe_emit(self.log_message, msg)

    def safe_emit(self, signal, *args):
        try:
            signal.emit(*args)
        except RuntimeError:
            pass

    # ------------------------------------------------------------------
    #  Dependency injection
    # ------------------------------------------------------------------
    def set_executor(self, executor):
        self.executor = executor
        logger.debug("🔗 Executor collegato") # ✅ LOG

    def set_trainer(self, trainer):
        self.trainer = trainer
        if trainer and self.executor:
            trainer.set_executor(self.executor)
        logger.debug("🔗 AITrainer collegato") # ✅ LOG

    def set_monitor(self, monitor):
        self.monitor = monitor
        if monitor and hasattr(monitor, 'set_recovery_callback'):
            monitor.set_recovery_callback(self._check_and_recover_browser)
        logger.debug("🔗 HealthMonitor collegato") # ✅ LOG

    def _check_and_recover_browser(self):
        if not self.executor:
            return
        with self._executor_lock:
            try:
                if not self.executor.check_health():
                    logger.warning("🚑 Browser non risponde — avvio recupero") # ✅ LOG
                    self.executor.recover_session()
            except Exception as e:
                logger.error(f"❌ Recupero browser fallito: {e}") # ✅ LOG

    def set_vision(self, vision):
        self.vision = vision

    def set_telegram_learner(self, telegram_learner):
        self.telegram_learner = telegram_learner

    def set_rpa_healer(self, rpa_healer):
        self.rpa_healer = rpa_healer

    def set_command_parser(self, parser):
        self.command_parser = parser
        logger.debug("🔗 CommandParser collegato")

    def set_watchdog(self, watchdog):
        self.watchdog = watchdog
        if watchdog:
            watchdog.browser_died.connect(self.on_browser_died)
            watchdog.resource_warning.connect(self._on_resource_warning)
            if hasattr(watchdog, 'request_recycle'):
                watchdog.request_recycle.connect(self._handle_recycle_request)
            logger.debug("🔗 SystemWatchdog collegato")

    def _handle_recycle_request(self):
        with self._executor_lock:
            if self.executor:
                logger.info("♻️ Riciclo Browser richiesto dal Watchdog") # ✅ LOG
                self.executor.recycle_browser()
                self.executor.launch_browser() 

    def _init_os_human(self):
        if self._os_human is None:
            try:
                from core.os_human_interaction import HumanOS
                self._os_human = HumanOS(self.logger)
                logger.info("🤖 HumanOS inizializzato (Safe Mode)") # ✅ LOG
            except Exception as e:
                logger.warning(f"⚠️ HumanOS non disponibile: {e}")

    # ------------------------------------------------------------------
    #  Boot sequence
    # ------------------------------------------------------------------
    def boot(self):
        with self._boot_lock:
            logger.info("🚀 V4 Boot sequence starting...") # ✅ LOG
            self.state_manager.transition(AgentState.IDLE)
            logger.info("✅ V4 Boot complete — State: IDLE")

    def start_system(self):
        def _async_boot():
            with self._boot_lock:
                if self._stop_event.is_set():
                    return
                logger.info("🚀 V4 Async Boot starting...") # ✅ LOG
                self.state_manager.transition(AgentState.IDLE)
                logger.info("✅ V4 Async Boot complete")
                
                if self.config.get("rpa", {}).get("cdp_watchdog", False):
                    self.start_cdp_watchdog()

        t = threading.Thread(target=_async_boot, name="controller-boot", daemon=True)
        t.start()

    # ------------------------------------------------------------------
    #  CDP Watchdog
    # ------------------------------------------------------------------
    def start_cdp_watchdog(self, interval: int = 60):
        def _watchdog():
            while not self._stop_event.is_set():
                self._stop_event.wait(interval)
                if self._stop_event.is_set():
                    break
                with self._executor_lock:
                    if self.executor and not self.executor.check_health():
                        logger.warning("🐕 CDP Watchdog: Browser Dead. Recovering...") # ✅ LOG
                        self.state_manager.set_state(AgentState.RECOVERING)
                        try:
                            self.executor.recover_session()
                            if not self._stop_event.is_set():
                                self.state_manager.set_state(AgentState.IDLE)
                            logger.info("🐕 CDP Watchdog: Recovery Success") # ✅ LOG
                        except Exception as e:
                            logger.error(f"🐕 CDP Watchdog: Recovery Failed: {e}") # ✅ LOG
                            self.state_manager.set_state(AgentState.ERROR)

        t = threading.Thread(target=_watchdog, name="cdp-watchdog", daemon=True)
        t.start()
        logger.info("👀 CDP Watchdog Started") # ✅ LOG

    # ------------------------------------------------------------------
    #  Watchdog Slots
    # ------------------------------------------------------------------
    @Slot()
    def on_browser_died(self):
        if self._stop_event.is_set():
            return
        logger.critical("💀 Browser DEATH detected! Starting SAFE recovery...") # ✅ LOG
        self.state_manager.set_state(AgentState.RECOVERING)

        def _recover():
            try:
                with self._executor_lock:
                    if self.executor:
                        try: self.executor.close()
                        except Exception: pass
                    
                    self._init_os_human()
                    if self._os_human:
                        logger.info("🧹 Cleaning residual Chrome processes...")
                        self._os_human.kill_chrome_processes() 

                    logger.info("🔄 Relaunching Browser (Internal)...")
                    if self.executor:
                        self.executor.recover_session() 
                        
                        if not self._stop_event.is_set():
                            self.state_manager.set_state(AgentState.IDLE)
                        logger.info("✅ Browser recuperato con successo (SAFE MODE)")

            except Exception as e:
                logger.critical(f"❌ Critical Recovery Failure: {e}")
                self.state_manager.set_state(AgentState.ERROR)

        t = threading.Thread(target=_recover, name="browser-recovery", daemon=True)
        t.start()

    @Slot(str)
    def _on_resource_warning(self, msg: str):
        logger.warning(f"⚠️ [Watchdog Resource]: {msg}") # ✅ LOG
        if self.executor and hasattr(self.executor, 'check_and_recycle'):
            try:
                with self._executor_lock:
                    self.executor.check_and_recycle()
            except Exception as e:
                logger.error(f"Memory check failed: {e}")

    # ------------------------------------------------------------------
    #  V4: Execution & Signal Handling
    # ------------------------------------------------------------------
    def handle_signal_v4(self, signal_data: dict) -> bool:
        if not self.command_parser:
            return self.handle_signal(signal_data)

        steps = self.command_parser.parse(signal_data)
        if not steps:
            logger.info("ℹ️ CommandParser: Nessuno step generato.") # ✅ LOG
            return False

        return self.execute_steps(steps)

    def execute_steps(self, steps) -> bool:
        if self._stop_event.is_set() or not self.executor:
            return False

        if not self.state_manager.transition(AgentState.NAVIGATING):
            logger.warning("⚠️ Impossibile transitare a NAVIGATING") # ✅ LOG
            return False

        if self.monitor:
            self.monitor.heartbeat()

        try:
            with self._executor_lock:
                selectors = self.executor._load_selectors()

                for step in steps:
                    logger.info(f"▶️ Esecuzione Step: {step.description or step.action}") # ✅ LOG
                    success = False
                    last_err = None

                    for attempt in range(step.retries + 1):
                        try:
                            success = self._execute_single_step(step, selectors)
                            if success:
                                break
                        except Exception as e:
                            last_err = e
                            logger.warning(f"⚠️ Step {step.action} fallito (tentativo {attempt+1}): {e}") # ✅ LOG
                            
                            # AI Healing
                            if step.heal_on_fail and self.rpa_healer and attempt < step.retries:
                                logger.info("🩹 Tentativo AI Healing...")
                                self.state_manager.set_state(AgentState.HEALING)
                                try:
                                    self.rpa_healer.heal()
                                    selectors = self.executor._load_selectors()
                                except Exception as heal_e:
                                    logger.error(f"❌ AI Healing fallito: {heal_e}")
                                self.state_manager.set_state(AgentState.NAVIGATING)

                    if not success:
                        logger.error(f"❌ Step {step.action} fallito definitivamente: {last_err}") # ✅ LOG
                        if not self._stop_event.is_set():
                            self.state_manager.set_state(AgentState.IDLE)
                        return False

            if not self._stop_event.is_set():
                self.state_manager.set_state(AgentState.IDLE)
            return True

        except Exception as e:
            logger.error(f"❌ Errore esecuzione step: {e}") # ✅ LOG
            self.state_manager.set_state(AgentState.ERROR)
            if not self._stop_event.is_set():
                self.state_manager.set_state(AgentState.IDLE)
            return False

    def _execute_single_step(self, step, selectors) -> bool:
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
            amount = params.get("amount")
            if not amount:
                teams_p = params.get("teams", "")
                market_p = params.get("market", "")
                odds, _loc = self.executor.find_odds(teams_p, market_p)
                amount = self.table.calculate_stake(odds) if odds > 1.0 else 0
            if not amount or amount <= 0:
                logger.info("ℹ️ Stake = 0, bet annullata") # ✅ LOG
                return False
            return self.executor.place_bet(
                params.get("teams", ""), params.get("market", ""),
                amount
            )
        else:
            logger.warning(f"⚠️ Step sconosciuto: {action}")
            return False

    def handle_signal(self, signal_data: dict) -> bool:
        """Legacy handler"""
        if self._stop_event.is_set():
            return False

        with self._signal_lock:
            self._signal_count += 1
            sig_num = self._signal_count

        teams = signal_data.get("teams", "")
        market = signal_data.get("market", "")
        logger.info(f"📨 Signal #{sig_num} Ricevuto: {teams} / {market}") # ✅ LOG

        if not self.executor:
            logger.error("❌ Nessun executor disponibile")
            return False

        if self.monitor:
            self.monitor.heartbeat()

        if not self.state_manager.transition(AgentState.NAVIGATING):
            logger.warning("⚠️ Impossibile transitare a NAVIGATING")
            return False

        try:
            with self._executor_lock:
                selectors = self.executor._load_selectors()

                # Login
                if not self.executor.ensure_login(selectors):
                    self.state_manager.transition(AgentState.ERROR)
                    logger.error("❌ Login fallito")
                    self.state_manager.transition(AgentState.IDLE)
                    return False

                # Navigate
                if teams and not self.executor.navigate_to_match(teams, selectors):
                    self.state_manager.transition(AgentState.ERROR)
                    logger.error(f"❌ Match non trovato: {teams}")
                    self.state_manager.transition(AgentState.IDLE)
                    return False

                # Select market
                if market and not self.executor.select_market(market, selectors):
                    self.state_manager.transition(AgentState.ERROR)
                    logger.error(f"❌ Mercato non trovato: {market}")
                    self.state_manager.transition(AgentState.IDLE)
                    return False

                # Betting
                self.state_manager.transition(AgentState.BETTING)
                odds, _loc = self.executor.find_odds(teams, market)
                stake = self.table.calculate_stake(odds) if odds > 1.0 else 0
                if not stake or stake <= 0:
                    logger.info("ℹ️ Stake calcolato = 0. Bet annullata.")
                    self.state_manager.transition(AgentState.IDLE)
                    return False
                
                result = self.executor.place_bet(teams, market, stake)

            # Record result
            self._bet_results.append({
                "teams": teams,
                "market": market,
                "placed": result,
                "timestamp": time.time(),
            })

            if result:
                logger.info("✅ BET PIAZZATA CON SUCCESSO!") # ✅ LOG
            else:
                logger.error("❌ Bet fallita in fase di piazzamento")

            if not self._stop_event.is_set():
                self.state_manager.transition(AgentState.IDLE)
            return result

        except Exception as e:
            logger.error(f"❌ Errore processamento segnale: {e}") # ✅ LOG
            self.state_manager.transition(AgentState.ERROR)
            # Recovery
            if self.executor:
                try:
                    self.state_manager.transition(AgentState.RECOVERING)
                    with self._executor_lock:
                        self.executor.recover_session()
                except Exception as recovery_err:
                    logger.critical(f"❌ Recovery fallita: {recovery_err}")
            if not self._stop_event.is_set():
                self.state_manager.transition(AgentState.IDLE)
            return False

    # ------------------------------------------------------------------
    #  AI Trainer interface
    # ------------------------------------------------------------------
    def ask_trainer(self, question: str,
                    include_dom: bool = False,
                    include_screenshot: bool = False) -> str:
        if not self.trainer:
            return "AI Trainer non disponibile."

        dom = None
        screenshot = None

        if include_dom and self.executor:
            try:
                with self._executor_lock:
                    dom = self.executor.get_dom_snapshot()
            except Exception as e:
                logger.warning(f"⚠️ DOM snapshot fallito: {e}")

        if include_screenshot and self.executor:
            try:
                with self._executor_lock:
                    screenshot = self.executor.take_screenshot_b64()
            except Exception as e:
                logger.warning(f"⚠️ Screenshot fallito: {e}")

        prev = self.state_manager.state
        self.state_manager.transition(AgentState.ANALYZING)
        try:
            logger.info(f"🗣️ Chiedo all'AI: {question}") # ✅ LOG
            result = self.trainer.ask(question, dom_snapshot=dom, screenshot_b64=screenshot)
            return result
        finally:
            if not self._stop_event.is_set():
                self.state_manager.force_state(prev)

    # ------------------------------------------------------------------
    #  Request Training (Async)
    # ------------------------------------------------------------------
    @Slot()
    def request_training(self):
        if not self.trainer:
            self.safe_emit(self.training_complete, "Trainer non disponibile.")
            return

        def _train():
            self.state_manager.set_state(AgentState.TRAINING)
            logger.info("🎓 Training AI avviato...") # ✅ LOG
            try:
                result = self.trainer.train_step()
                logger.info(f"✅ Training completato. Risposta: {len(result)} chars") # ✅ LOG
                self.safe_emit(self.training_complete, result)
            except Exception as e:
                logger.error(f"❌ Training fallito: {e}") # ✅ LOG
                self.safe_emit(self.training_complete, f"Errore training: {e}")
            finally:
                if not self._stop_event.is_set():
                    self.state_manager.set_state(AgentState.IDLE)

        t = threading.Thread(target=_train, name="training-thread", daemon=True)
        t.start()

    def clear_trainer_memory(self):
        if self.trainer:
            self.trainer.clear_memory()
            logger.info("🧹 Memoria AI Trainer pulita")

    # ------------------------------------------------------------------
    #  Status / Stats
    # ------------------------------------------------------------------
    def get_state(self) -> str:
        return self.state_manager.state.name

    def get_stats(self) -> dict:
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
        return self.state_manager.get_history(n)

    # ------------------------------------------------------------------
    #  Stealth mode
    # ------------------------------------------------------------------
    def set_stealth_mode(self, mode: str):
        if self.executor and hasattr(self.executor, 'stealth_mode'):
            self.executor.stealth_mode = mode
            logger.info(f"🥷 Stealth Mode impostata a: {mode}") # ✅ LOG

    def get_stealth_mode(self) -> str:
        if self.executor and hasattr(self.executor, 'stealth_mode'):
            return self.executor.stealth_mode
        return "balanced"

    # ------------------------------------------------------------------
    #  Auto-Mapping
    # ------------------------------------------------------------------
    def request_auto_mapping(self, url):
        api_key = self.vault.decrypt_data().get("openrouter_api_key")

        if not api_key:
            logger.error("❌ API Key mancante per Auto-Mapping")
            self.safe_emit(self.log_message, "API Key mancante")
            return

        if hasattr(self, '_mapper_thread') and self._mapper_thread and self._mapper_thread.isRunning():
            self._mapper_thread.quit()
            self._mapper_thread.wait(3000)

        with self._executor_lock:
            if self.executor and self.executor.page:
                if self.executor.page.url != url:
                    logger.info(f"🧭 Navigazione Auto-Map verso: {url}")
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
        self.mapper_worker.error.connect(lambda e: logger.error(f"❌ Errore Mapping: {e}"))
        self.mapper_worker.finished.connect(self._mapper_thread.quit)
        self.mapper_worker.error.connect(self._mapper_thread.quit)
        self._mapper_thread.start()
        logger.info("🗺️ Auto-Mapping avviato...")

    def on_mapping_success(self, result_dict):
        import yaml
        yaml_code = yaml.dump(result_dict, default_flow_style=False)
        logger.info("✅ Auto-Mapping completato con successo")
        self.safe_emit(self.mapping_ready, yaml_code)

    def test_mapping_visual(self, yaml_code):
        with self._executor_lock:
            if self.executor:
                self.executor.highlight_selectors(yaml_code)

    def save_selectors_yaml(self, yaml_code):
        import os
        _root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        yaml_path = os.path.join(_root, "config", "selectors.yaml")
        try:
            with open(yaml_path, "w", encoding="utf-8") as f:
                f.write(yaml_code)
            logger.info(f"💾 Selectors salvati in {yaml_path}")
            self.safe_emit(self.log_message, f"selectors.yaml salvato in: {yaml_path}")
        except Exception as e:
            logger.error(f"❌ Errore salvataggio YAML: {e}")

    # ------------------------------------------------------------------
    #  Telegram Connection
    # ------------------------------------------------------------------
    def connect_telegram(self, config):
        self.vault.encrypt_data(config)
        self.current_config = config

        if self.telegram_worker:
            self.telegram_worker.stop()

        from core.telegram_worker import TelegramWorker
        logger.info("🔄 Riavvio TelegramWorker con nuova configurazione...")
        self.telegram_worker = TelegramWorker(config)
        self.telegram_worker.message_received.connect(self.handle_telegram_signal)
        self.telegram_worker.start()

    # ------------------------------------------------------------------
    #  Roserpina Handler
    # ------------------------------------------------------------------
    def handle_telegram_signal(self, text):
        logger.info(f"📨 Ricevuto da Telegram: {text[:50]}...") # ✅ LOG
        
        # 1. Check Pendente
        if self.table.is_pending:
            logger.warning("⚠️ Scommessa in corso, segnale ignorato.")
            self.safe_emit(self.log_message, "⚠️ Scommessa in corso, segnale ignorato.")
            return

        # 2. Parsing
        data = self.parser.parse(text)
        if not data['match']:
            logger.debug("ℹ️ Testo ignorato (non è un segnale valido)")
            return

        logger.info(f"🎯 Segnale parsato: {data}")
        
        # 3. Avvio Thread Scommessa
        self.table.is_pending = True
        self.bet_worker = BetWorker(self.table, self.executor, data)

        self.bet_worker.finished.connect(self.on_bet_complete)
        self.bet_worker.start()

    def on_bet_complete(self, result):
        self.table.is_pending = False
        if result:
            logger.info("✅ BetWorker: Successo")
            self.safe_emit(self.log_message, "Bet Piazzata")
        else:
            logger.error("❌ BetWorker: Fallimento")
            self.safe_emit(self.log_message, "Errore Bet")

    # ------------------------------------------------------------------
    #  Shutdown
    # ------------------------------------------------------------------
    def shutdown(self):
        logger.info("🔻 Shutdown Sistema Iniziato") # ✅ LOG
        self._stop_event.set()
        self.state_manager.force_state(AgentState.SHUTDOWN)
        with self._executor_lock:
            if self.executor:
                try:
                    self.executor.close()
                except Exception as recovery_exc:
                    logger.error(f"❌ Errore chiusura executor: {recovery_exc}")
        logger.info("🏁 Shutdown Completato. Bye.")
