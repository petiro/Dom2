import threading
import queue
import logging
from typing import Callable, Dict, List, Any


class EventBus:
    """
    Thread-safe asynchronous event bus.

    Features:
    - Background dispatcher thread
    - Safe shutdown with join
    - No silent exception swallowing
    - Multiple subscribers per event
    """

    def __init__(self):
        self._subscribers: Dict[Any, List[Callable]] = {}
        self._queue: queue.Queue = queue.Queue()
        self._running: bool = False
        self._dispatcher: threading.Thread | None = None
        self._lock = threading.Lock()
        self.logger = logging.getLogger(self.__class__.__name__)

    # -------------------------
    # Public API
    # -------------------------

    def subscribe(self, event: Any, callback: Callable):
        """Subscribe a callback to an event."""
        with self._lock:
            if event not in self._subscribers:
                self._subscribers[event] = []
            self._subscribers[event].append(callback)

    def emit(self, event: Any, payload=None):
        """Emit an event asynchronously."""
        if not self._running:
            return
        self._queue.put((event, payload or {}))

    def start(self):
        """Start dispatcher thread."""
        if self._running:
            return

        self._running = True
        self._dispatcher = threading.Thread(
            target=self._dispatch_loop,
            daemon=True,
            name="EventBus_Dispatcher"
        )
        self._dispatcher.start()

    def stop(self):
        """Stops the dispatcher thread safely and idempotently."""
        if not self._running:
            return

        self._running = False
        try:
            if self._dispatcher and self._dispatcher.is_alive():
                self._dispatcher.join(timeout=2.0)
        except Exception as e:
            self.logger.warning(
                f"Error stopping EventBus dispatcher thread: {e}"
            )

    # -------------------------
    # Internal
    # -------------------------

    def _dispatch_loop(self):
        """Background dispatch loop."""
        while self._running:
            try:
                event, payload = self._queue.get(timeout=0.5)

                with self._lock:
                    callbacks = list(self._subscribers.get(event, []))

                for callback in callbacks:
                    try:
                        callback(payload)
                    except Exception as e:
                        self.logger.error(
                            f"Error in event callback for {event}: {e}"
                        )

                self._queue.task_done()

            except queue.Empty:
                continue
            except Exception as e:
                self.logger.error(f"EventBus dispatch error: {e}")


# Singleton instance (auto-started)
bus = EventBus()
bus.start()
