import threading
import queue
import time


# --- 1. EVENT BUS CENTRALE ---
class EventBusV6:
    def __init__(self, logger):
        self.logger = logger
        self.listeners = {}
        self.lock = threading.Lock()

    def subscribe(self, event, fn):
        with self.lock:
            if event not in self.listeners:
                self.listeners[event] = []
            self.listeners[event].append(fn)

    def emit(self, event, data=None):
        with self.lock:
            listeners = list(self.listeners.get(event, []))

        for fn in listeners:
            try:
                threading.Thread(target=fn, args=(data,), daemon=True).start()
            except Exception as e:
                self.logger.error(f"EventBus Error ({event}): {e}")


# --- 2. PLAYWRIGHT WORKER (Anti-Freeze) ---
class PlaywrightWorker:
    def __init__(self, executor, logger):
        self.executor = executor
        self.logger = logger
        self.queue = queue.Queue()
        self.running = True
        self.thread = threading.Thread(target=self._loop, daemon=True, name="PW_Worker")
        self.thread.start()

    def submit(self, fn, *args, **kwargs):
        """Aggiunge un task alla coda di Playwright."""
        self.queue.put((fn, args, kwargs))

    def _loop(self):
        self.logger.info("Worker Playwright avviato.")
        while self.running:
            try:
                fn, args, kwargs = self.queue.get(timeout=1)
                fn(*args, **kwargs)
                self.queue.task_done()
                self.logger.debug(f"Worker task completato: {fn.__name__}")
            except queue.Empty:
                continue
            except Exception as e:
                self.logger.error(f"Worker Error: {e}")

    def stop(self):
        self.running = False


# --- 3. SESSION GUARDIAN (Auto-Recovery) ---
class SessionGuardian:
    def __init__(self, executor, logger):
        self.executor = executor
        self.logger = logger
        self.stop_event = threading.Event()
        self._consecutive_failures = 0
        self._max_failures = 3  # 3 check falliti prima di recovery

    def start(self):
        threading.Thread(target=self._loop, daemon=True, name="SessionGuardian").start()

    def _loop(self):
        self.logger.info("Session Guardian attivo (check ogni 15s, recovery dopo 3 fail).")
        while not self.stop_event.wait(15):
            try:
                if not self.executor.check_health():
                    self._consecutive_failures += 1
                    self.logger.warning(
                        f"Browser unhealthy ({self._consecutive_failures}/{self._max_failures})"
                    )
                    if self._consecutive_failures >= self._max_failures:
                        self._do_recovery()
                        self._consecutive_failures = 0
                else:
                    # Reset counter se il browser risponde
                    if self._consecutive_failures > 0:
                        self.logger.info("Browser tornato healthy.")
                    self._consecutive_failures = 0
            except Exception as e:
                self.logger.error(f"Guardian Error: {e}")

    def _do_recovery(self):
        """Esegue recovery adattivo: attached mode vs standalone."""
        self.logger.warning("Recovery automatico in corso...")
        try:
            if hasattr(self.executor, 'recover_session'):
                self.executor.recover_session()
            elif getattr(self.executor, "is_attached", False):
                # Attached: tenta ri-aggancio senza chiudere Chrome
                self.executor._initialized = False
                self.executor.pw = None
                self.executor.browser = None
                self.executor.page = None
                self.executor.human = None
                self.executor.launch_browser()
            else:
                self.executor.recycle_browser()
        except Exception as e:
            self.logger.error(f"Recovery fallito: {e}")

    def stop(self):
        self.stop_event.set()


# --- 4. PLAYWRIGHT WATCHDOG (Thread Monitor) ---
class PlaywrightWatchdog:
    def __init__(self, worker, logger):
        self.worker = worker
        self.logger = logger
        self.stop_event = threading.Event()

    def start(self):
        threading.Thread(target=self._loop, daemon=True, name="PW_Watchdog").start()

    def _loop(self):
        while not self.stop_event.wait(20):
            if self.worker.running and not self.worker.thread.is_alive():
                self.logger.critical("ALLARME: Il thread Playwright Worker è morto! Riavvio...")
                self._restart_worker()

    def _restart_worker(self):
        """Tenta di riavviare il Worker thread."""
        try:
            self.worker.thread = threading.Thread(
                target=self.worker._loop, daemon=True, name="PW_Worker"
            )
            self.worker.thread.start()
            self.logger.info("Worker Playwright riavviato dal Watchdog.")
        except Exception as e:
            self.logger.error(f"Watchdog: impossibile riavviare Worker: {e}")

    def stop(self):
        self.stop_event.set()
