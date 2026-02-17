import threading
import queue
import logging
from typing import Callable, Dict, List, Any


class EventBus:
    def __init__(self):
        self._subscribers: Dict[Any, List[Callable]] = {}
        self._queue: queue.Queue = queue.Queue()
        self._running = False
        self._dispatcher = None
        self.logger = logging.getLogger("EventBus")

    def subscribe(self, event: Any, callback: Callable):
        self._subscribers.setdefault(event, []).append(callback)

    def emit(self, event: Any, payload: dict | None = None):
        if self._running:
            self._queue.put((event, payload or {}))

    def start(self):
        if self._running:
            return
        self._running = True
        self._dispatcher = threading.Thread(
            target=self._dispatch_loop,
            daemon=True
        )
        self._dispatcher.start()

    def stop(self):
        self._running = False
        if self._dispatcher:
            self._dispatcher.join(timeout=5)

    def _dispatch_loop(self):
        while self._running or not self._queue.empty():
            try:
                event, payload = self._queue.get(timeout=0.5)
                for cb in self._subscribers.get(event, []):
                    try:
                        cb(payload)
                    except Exception as e:
                        self.logger.error(f"Callback error: {e}")
                self._queue.task_done()
            except queue.Empty:
                continue


# ✅ Fix BUG IMPORT
bus = EventBus()