import threading
import queue
import logging
from typing import Callable, Dict, List, Any

class EventBus:
    def __init__(self):
        self._subscribers: Dict[Any, List[Callable]] = {}
        self._queue: queue.Queue = queue.Queue()
        self._running: bool = False
        self._dispatcher: threading.Thread | None = None
        self.logger = logging.getLogger(self.__class__.__name__)

    def subscribe(self, event: Any, callback: Callable):
        if event not in self._subscribers: self._subscribers[event] = []
        self._subscribers[event].append(callback)

    def emit(self, event: Any, payload: dict | None = None):
        if self._running: self._queue.put((event, payload or {}))

    def start(self):
        if self._running: return
        self._running = True
        self._dispatcher = threading.Thread(target=self._dispatch_loop, daemon=True)
        self._dispatcher.start()

    def stop(self):
        self._running = False
        if self._dispatcher and self._dispatcher.is_alive():
            self._dispatcher.join(timeout=2.0)

    def _dispatch_loop(self):
        while self._running:
            try:
                event, payload = self._queue.get(timeout=0.5)
                for cb in self._subscribers.get(event, []):
                    try: cb(payload)
                    except: pass
                self._queue.task_done()
            except queue.Empty: continue