import time
import threading
import socket


# FIX BUG-06: Solo HealthMonitor qui. SystemWatchdog completo e in core/lifecycle.py
class HealthMonitor:
    MAX_RESTARTS = 3
    COOLDOWN = 300

    def __init__(self, logger, executor=None):
        self.logger = logger
        self.executor = executor
        self._stop_event = threading.Event()
        self._restart_lock = threading.Lock()
        self._restart_count = 0
        self._last_restart = 0
        self._restarting = False

    def start(self):
        threading.Thread(target=self._monitor, daemon=True).start()

    def _monitor(self):
        while not self._stop_event.is_set():
            time.sleep(60)
            if self._stop_event.is_set():
                break
            self._check_internet()

    def _check_internet(self):
        try:
            with socket.create_connection(("8.8.8.8", 53), timeout=3):
                pass
        except Exception:
            self.logger.warning("⚠️ Internet non raggiungibile.")

    def safe_restart(self, restart_fn=None):
        with self._restart_lock:
            now = time.time()
            if self._restarting:
                return False

            if now - self._last_restart > self.COOLDOWN:
                self._restart_count = 0

            if self._restart_count >= self.MAX_RESTARTS:
                self.logger.error("❌ Limite riavvii raggiunto.")
                return False

            self._restarting = True
            self._restart_count += 1
            self._last_restart = now

        try:
            if restart_fn:
                restart_fn()
        finally:
            with self._restart_lock:
                self._restarting = False
        return True

    def stop(self):
        self._stop_event.set()
