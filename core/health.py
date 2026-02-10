"""
HealthMonitor — Centralised Immortality Layer for SuperAgent H24.

Manages:
  - Heartbeat / freeze detection (5 min timeout → hard restart)
  - Browser health check + auto-recovery
  - Memory guard with averaged samples (>1.5 GB avg → restart)
  - Scheduled maintenance restart (04:00 every day)
  - Internet fail-safe (sleep instead of restart when offline)
  - Double-restart race-condition lock
"""
import os
import sys
import time
import socket
import threading
from datetime import datetime


class HealthMonitor:
    """Central fault-tolerance coordinator.

    Usage:
        monitor = HealthMonitor(logger, executor)
        monitor.run_forever()          # launches daemon threads
        monitor.heartbeat()            # call from any active module
    """

    FREEZE_TIMEOUT = 300        # seconds (5 min)
    MEMORY_LIMIT_MB = 1500      # restart if avg exceeds this
    MEMORY_SAMPLES = 3          # average over N cycles
    MONITOR_INTERVAL = 30       # seconds between checks
    MAINTENANCE_HOUR = 4        # 04:00 daily restart

    def __init__(self, logger, executor=None):
        self.logger = logger
        self.executor = executor
        self.last_heartbeat = time.time()
        self.start_time = datetime.now()
        self._stop_event = threading.Event()
        self._restarting = False          # race-condition guard
        self._mem_samples: list[float] = []

    # ------------------------------------------------------------------
    #  Public API
    # ------------------------------------------------------------------
    def heartbeat(self):
        """Signal that the system is alive.  Call from RPA, Telegram, UI."""
        self.last_heartbeat = time.time()

    def set_executor(self, executor):
        """Attach (or replace) the browser executor after init."""
        self.executor = executor

    def run_forever(self):
        """Start all daemon monitoring threads."""
        threading.Thread(target=self._monitor_loop, daemon=True,
                         name="HealthMonitor-main").start()
        threading.Thread(target=self._maintenance_loop, daemon=True,
                         name="HealthMonitor-maintenance").start()
        # Keep the old heartbeat_worker alive for backward compat with
        # `import main; main.last_heartbeat`
        threading.Thread(target=self._heartbeat_sync, daemon=True,
                         name="HealthMonitor-hb-sync").start()
        self.logger.info("[HealthMonitor] All monitoring threads started")

    # ------------------------------------------------------------------
    #  Internet check
    # ------------------------------------------------------------------
    @staticmethod
    def internet_alive(timeout: int = 5) -> bool:
        """Quick connectivity probe (Google DNS)."""
        try:
            socket.create_connection(("8.8.8.8", 53), timeout=timeout)
            return True
        except OSError:
            return False

    # ------------------------------------------------------------------
    #  Internal loops
    # ------------------------------------------------------------------
    def _monitor_loop(self):
        while not self._stop_event.is_set():
            time.sleep(self.MONITOR_INTERVAL)

            # --- Internet fail-safe: sleep, don't restart ---
            if not self.internet_alive():
                self.logger.warning("[HealthMonitor] No internet — sleeping 60s")
                time.sleep(60)
                continue

            # --- 1. Freeze detection ---
            elapsed = time.time() - self.last_heartbeat
            if elapsed > self.FREEZE_TIMEOUT:
                self.logger.critical(
                    f"[HealthMonitor] FREEZE DETECTED ({elapsed:.0f}s) — restarting")
                self._hard_restart()
                return

            # --- 2. Browser health ---
            if self.executor:
                try:
                    if not self.executor.check_health():
                        self.logger.warning(
                            "[HealthMonitor] Browser unresponsive — recovering")
                        self.executor.recover_session()
                except Exception as e:
                    self.logger.error(f"[HealthMonitor] Browser check error: {e}")

            # --- 3. Memory guard (averaged) ---
            try:
                import psutil
                mem_mb = psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024)
                self._mem_samples.append(mem_mb)
                if len(self._mem_samples) > self.MEMORY_SAMPLES:
                    self._mem_samples.pop(0)
                avg = sum(self._mem_samples) / len(self._mem_samples)
                if avg > self.MEMORY_LIMIT_MB:
                    self.logger.warning(
                        f"[HealthMonitor] High avg memory {avg:.0f} MB — restarting")
                    self._hard_restart()
                    return
            except ImportError:
                pass  # psutil not installed — skip memory guard
            except Exception:
                pass

    def _maintenance_loop(self):
        """Daily restart at MAINTENANCE_HOUR for memory hygiene."""
        while not self._stop_event.is_set():
            now = datetime.now()
            if now.hour == self.MAINTENANCE_HOUR and now.minute == 0:
                self.logger.info(
                    "[HealthMonitor] Scheduled maintenance restart (04:00)")
                self._hard_restart()
                return
            time.sleep(60)

    def _heartbeat_sync(self):
        """Keep `main.last_heartbeat` in sync for backward compatibility."""
        while not self._stop_event.is_set():
            try:
                import main as _m
                _m.last_heartbeat = self.last_heartbeat
            except Exception:
                pass
            time.sleep(10)

    # ------------------------------------------------------------------
    #  Hard restart (with race-condition lock)
    # ------------------------------------------------------------------
    def _hard_restart(self):
        if self._restarting:
            return
        self._restarting = True
        self.logger.critical("[HealthMonitor] RESTART DI EMERGENZA")
        try:
            if sys.platform == "win32":
                os.startfile(sys.executable)  # pylint: disable=no-member
            sys.exit(0)
        except Exception:
            os._exit(1)
