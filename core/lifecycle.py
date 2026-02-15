"""
System Lifecycle & Watchdog — Thread-safe process health monitoring.

Features:
  - Memory watchdog (RAM usage monitoring)
  - Browser process detection (Chrome alive check)
  - Signal-based restart requests (Qt thread-safe)
  - Resource warnings emitted as Qt Signals

Uses psutil for process monitoring, emits Qt Signals for thread safety
(never touches Playwright directly from the watchdog thread).
"""
import time

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

from PySide6.QtCore import QThread, Signal


class SystemWatchdog(QThread):
    """Background thread that monitors system health.

    Emits signals instead of directly manipulating objects
    to maintain thread safety with Qt and Playwright.
    """
    request_restart = Signal()
    resource_warning = Signal(str)
    browser_died = Signal()
    request_recycle = Signal()

    def __init__(self, check_interval: int = 30, executor=None, logger=None):
        super().__init__()
        self._running = True
        self._check_interval = check_interval
        self.executor = executor
        self.logger = logger

    def stop(self):
        self._running = False

    def run(self):
        while self._running:
            time.sleep(self._check_interval)
            if not self._running:
                break

            # 1. Memory watchdog
            if PSUTIL_AVAILABLE:
                try:
                    mem = psutil.virtual_memory()
                    if mem.percent > 90:
                        self.resource_warning.emit(
                            f"RAM critica: {mem.percent}% utilizzata ({mem.used // (1024*1024)} MB)")
                    elif mem.percent > 80:
                        self.resource_warning.emit(
                            f"RAM alta: {mem.percent}% utilizzata")
                except Exception as e:
                    if self.logger:
                        self.logger.warning(f"[Watchdog] Check failed: {e}")

                # 2. Check if Chrome is still running
                try:
                    chrome_alive = any(
                        'chrome' in p.info.get('name', '').lower()
                        for p in psutil.process_iter(['name'])
                    )
                    if not chrome_alive:
                        self.browser_died.emit()
                except Exception as e:
                    if self.logger:
                        self.logger.warning(f"[Watchdog] Check failed: {e}")

            # 3. Process-level memory check (own process)
            if PSUTIL_AVAILABLE:
                try:
                    own_proc = psutil.Process()
                    own_mb = own_proc.memory_info().rss / (1024 * 1024)
                    if own_mb > 2000:  # >2GB
                        self.resource_warning.emit(
                            f"Processo SuperAgent usa {own_mb:.0f} MB RAM")
                except Exception as e:
                    if self.logger:
                        self.logger.warning(f"[Watchdog] Check failed: {e}")

            # 4. Browser memory recycle trigger (pure psutil, no executor dependency)
            if PSUTIL_AVAILABLE:
                try:
                    parent = psutil.Process()
                    browser_mem = 0
                    for child in parent.children(recursive=True):
                        if "chrome" in child.name().lower():
                            browser_mem += child.memory_info().rss
                    browser_mb = browser_mem / (1024 * 1024)
                    if browser_mb > 1500:  # 1.5GB
                        if self.logger:
                            self.logger.warning(f"[Watchdog] High Browser Memory ({browser_mb:.0f} MB) - Requesting Recycle")
                        self.request_recycle.emit()
                except Exception as e:
                    if self.logger:
                        self.logger.warning(f"[Watchdog] Browser memory check failed: {e}")
