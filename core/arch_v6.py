import threading
import queue
import time

# Constants
JOIN_TIMEOUT = 2
HEALTH_CHECK_INTERVAL = 15
WATCHDOG_INTERVAL = 20


# --- 1. CENTRAL EVENT BUS ---
class EventBusV6:
    """Pub/Sub with single dispatcher thread (avoids thread-per-event explosion)."""

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
        """Enqueues the event; the dispatcher delivers it to listeners."""
        self._queue.put((event, data))

    def _dispatch_loop(self):
        """Single thread that processes all events in order."""
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
        # Drain remaining events
        while not self._queue.empty():
            try:
                event, data = self._queue.get_nowait()
                self.logger.debug(f"Draining event on stop: {event}")
                self._queue.task_done()
            except queue.Empty:
                break
        try:
            self._dispatcher.join(timeout=JOIN_TIMEOUT)
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
        """Adds a task to the Playwright queue."""
        self.queue.put((fn, args, kwargs))

    def _loop(self):
        self.logger.info("Playwright Worker started.")
        while self.running:
            try:
                fn, args, kwargs = self.queue.get(timeout=1)
                fn(*args, **kwargs)
                self.queue.task_done()
                self.logger.debug(f"Worker task completed: {fn.__name__}")
            except queue.Empty:
                continue
            except Exception as e:
                self.logger.error(f"Worker Error: {e}")

    def stop(self):
        self.running = False


# --- 3. SESSION GUARDIAN (Auto-Recovery) ---
class SessionGuardian:
    MAX_FAILURES = 3

    def __init__(self, executor, logger):
        self.executor = executor
        self.logger = logger
        self.stop_event = threading.Event()
        self._consecutive_failures = 0

    def start(self):
        threading.Thread(target=self._loop, daemon=True, name="SessionGuardian").start()

    def _loop(self):
        self.logger.info(
            f"Session Guardian active (check every {HEALTH_CHECK_INTERVAL}s, "
            f"recovery after {self.MAX_FAILURES} fails)."
        )
        while not self.stop_event.wait(HEALTH_CHECK_INTERVAL):
            try:
                if not self.executor.check_health():
                    self._consecutive_failures += 1
                    self.logger.warning(
                        f"Browser unhealthy ({self._consecutive_failures}/{self.MAX_FAILURES})"
                    )
                    if self._consecutive_failures >= self.MAX_FAILURES:
                        self._do_recovery()
                        self._consecutive_failures = 0
                else:
                    if self._consecutive_failures > 0:
                        self.logger.info("Browser back to healthy.")
                    self._consecutive_failures = 0
            except Exception as e:
                self.logger.error(f"Guardian Error: {e}")

    def _do_recovery(self):
        """Delegates the recovery process to the executor."""
        self.logger.warning("Automatic recovery in progress...")
        try:
            if hasattr(self.executor, "recover_session"):
                success = self.executor.recover_session()
            elif (
                hasattr(self.executor, "recycle_browser")
                and not getattr(self.executor, "is_attached", False)
            ):
                success = self.executor.recycle_browser()
            else:
                self.logger.error(
                    "Automatic recovery not possible with current executor configuration."
                )
                return

            if success:
                self.logger.info("Recovery completed successfully.")
            else:
                self.logger.error("Recovery attempt failed.")
        except Exception as e:
            self.logger.error(f"Recovery process crashed: {e}", exc_info=True)

    def stop(self):
        self.stop_event.set()


# --- 4. PLAYWRIGHT WATCHDOG (Thread Monitor) ---
class PlaywrightWatchdog:
    def __init__(self, worker, logger):
        self.worker = worker
        self.logger = logger
        self.stop_event = threading.Event()
        self._restart_lock = threading.Lock()

    def start(self):
        threading.Thread(target=self._loop, daemon=True, name="PW_Watchdog").start()

    def _loop(self):
        while not self.stop_event.wait(WATCHDOG_INTERVAL):
            if self.worker.running and not self.worker.thread.is_alive():
                self.logger.critical("ALERT: Playwright Worker thread is dead! Restarting...")
                self._restart_worker()

    def _restart_worker(self):
        """Attempts to restart the Worker thread (thread-safe)."""
        with self._restart_lock:
            try:
                if self.worker.thread.is_alive():
                    return  # Already restarted by another check
                self.worker.thread = threading.Thread(
                    target=self.worker._loop, daemon=True, name="PW_Worker"
                )
                self.worker.thread.start()
                self.logger.info("Playwright Worker restarted by Watchdog.")
            except Exception as e:
                self.logger.error(f"Watchdog: cannot restart Worker: {e}")

    def stop(self):
        self.stop_event.set()
