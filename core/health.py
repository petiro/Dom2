"""
HealthMonitor — Centralised Immortality Layer for SuperAgent H24.

Manages:
  - Heartbeat / freeze detection (5 min timeout -> hard restart)
  - Browser health check + auto-recovery
  - Memory guard with averaged samples (>1.5 GB avg -> restart)
  - Scheduled maintenance restart (04:00 every day)
  - Internet fail-safe (sleep instead of restart when offline)
  - Double-restart race-condition lock
  - SystemWatchdog (Qt based) per integrazione GUI
"""
import os
import sys
import time
import socket
import threading
from datetime import datetime

# Import Qt per il Watchdog GUI
try:
    from PySide6.QtCore import QObject, Signal, QTimer
    import psutil
except ImportError:
    # Mock per ambienti senza GUI/psutil (CI/CD)
    class QObject: pass
    def Signal(*args): pass
    class QTimer: pass

# ============================================================================
#  CLASS 1: SystemWatchdog (Qt/GUI Integration)
#  Usato dal Controller per gestire eventi senza killare il processo
# ============================================================================
class SystemWatchdog(QObject):
    """
    Watchdog specifico per la GUI (Qt) che comunica col Controller via Signals.
    Monitora RAM e processi in modo 'gentile'.
    """
    browser_died = Signal()
    resource_warning = Signal(str)
    request_recycle = Signal()

    def __init__(self, interval_ms=30000):
        super().__init__()
        # Timer interno Qt che gira nel thread principale
        self._timer = None
        if 'QTimer' in globals() and hasattr(QTimer, 'timeout'):
            self._timer = QTimer()
            self._timer.timeout.connect(self._check_health)
            self._timer.start(interval_ms)

    def _check_health(self):
        """Controllo periodico risorse."""
        try:
            # 1. Controllo Memoria Processo Corrente
            process = psutil.Process(os.getpid())
            mem_mb = process.memory_info().rss / (1024 * 1024)
            
            if mem_mb > 1200: # Warning a 1.2GB
                self.resource_warning.emit(f"High RAM usage: {mem_mb:.0f} MB")
            
            if mem_mb > 1800: # Richiesta Riciclo a 1.8GB
                self.request_recycle.emit()

        except Exception:
            pass

# ============================================================================
#  CLASS 2: HealthMonitor (Legacy/Thread based)
#  Usato per hard-restart in caso di freeze totale
# ============================================================================
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
        # Callback for browser recovery (set by controller for thread safety)
        self._on_browser_unhealthy = None

    # ------------------------------------------------------------------
    #  Public API
    # ------------------------------------------------------------------
    def heartbeat(self):
        """Signal that the system is alive.  Call from RPA, Telegram, UI."""
        self.last_heartbeat = time.time()

    def set_executor(self, executor):
        """Attach (or replace) the browser executor after init."""
        self.executor = executor

    def set_recovery_callback(self, callback):
        """Set callback for browser recovery (called from monitor thread)."""
        self._on_browser_unhealthy = callback

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

            # --- 2. Browser health (via callback, no direct Playwright access) ---
            if self._on_browser_unhealthy:
                try:
                    self._on_browser_unhealthy()
                except Exception as e:
                    self.logger.error(f"[HealthMonitor] Browser recovery callback error: {e}")

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
                # import main as _m
                # _m.last_heartbeat = self.last_heartbeat
                pass # Disabilitato per evitare circular imports in V5.5
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
            else:
                import subprocess
                subprocess.Popen([sys.executable] + sys.argv)
            sys.exit(0)
        except Exception:
            os._exit(1)
