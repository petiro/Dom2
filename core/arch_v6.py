import threading
import queue
import time


# --- 1. EVENT BUS CENTRALE ---
class EventBusV6:
    """Pub/Sub con singolo dispatcher thread (evita thread-per-event explosion)."""

    def __init__(self, logger):
        self.logger = logger
        self.listeners = {}
        self.lock = threading.Lock()
        self._queue = queue.Queue()
        self._running = True
        self._dispatcher = threading.Thread(
            target=self._dispatch_loop, daemon=True, name="EventBus_Dispatcher"
        )
        self._dispatcher.start()

    def subscribe(self, event, fn):
        with self.lock:
            if event not in self.listeners:
                self.listeners[event] = []
            self.listeners[event].append(fn)

    def emit(self, event, data=None):
        """Accoda l'evento; il dispatcher lo consegna ai listener."""
        self._queue.put((event, data))

    def _dispatch_loop(self):
        """Singolo thread che processa tutti gli eventi in ordine."""
        while self._running:
            try:
                event, data = self._queue.get(timeout=1)
            except queue.Empty:
                continue
            with self.lock:
                listeners = list(self.listeners.get(event, []))
            for fn in listeners:
                try:
                    fn(data)
                except Exception as e:
                    self.logger.error(f"EventBus Error ({event}): {e}")
            self._queue.task_done()

    def stop(self):
        self._running = False
        try:
            self._dispatcher.join(timeout=2)
        except Exception as e:
            self.logger.warning(f"Error stopping EventBusV6 dispatcher: {e}")


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
        """Delega il processo di recovery all'executor."""
        self.logger.warning("Recovery automatico in corso...")
        try:
            if hasattr(self.executor, 'recover_session'):
                self.executor.recover_session()
            else:
                self.logger.warning("L'executor non implementa 'recover_session'. Fallback a 'recycle_browser'.")
                if not getattr(self.executor, "is_attached", False):
                    self.executor.recycle_browser()
                else:
                    self.logger.error("Recovery automatico non possibile in modalita 'attached' con un executor obsoleto.")
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
