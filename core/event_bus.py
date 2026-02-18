import threading
import queue
import logging
import time
from typing import Callable, Dict, List, Any

class EventBus:
    def __init__(self):
        self._subscribers: Dict[Any, List[Callable]] = {}
        self._queue: queue.Queue = queue.Queue()
        self._running: bool = False
        self._dispatcher: threading.Thread | None = None
        self.logger = logging.getLogger("EventBus")

    def subscribe(self, event: Any, callback: Callable):
        self._subscribers.setdefault(event, []).append(callback)

    def emit(self, event: Any, payload: dict | None = None):
        if not self._running:
            return

        if self._queue.qsize() > 5000:
            self.logger.warning("EventBus queue overflow. Dropping event.")
            return

        self._queue.put((event, payload or {}))

    def start(self):
        if self._running: return
        self._running = True
        self._dispatcher = threading.Thread(target=self._dispatch_loop, daemon=True)
        self._dispatcher.start()

    def stop(self):
        self._running = False
        if self._dispatcher: self._dispatcher.join(timeout=3)

    def _dispatch_loop(self):
        while self._running or not self._queue.empty():
            try:
                event, payload = self._queue.get(timeout=0.5)
                
                callbacks = self._subscribers.get(event, [])
                for cb in callbacks:
                    try:
                        cb(payload)
                    except Exception:
                        self.logger.exception(f"[EventBus] callback crash on {event}")

                self._queue.task_done()

            except queue.Empty:
                continue
            except Exception:
                self.logger.exception("🔥 EventBus dispatcher crash prevented")
                time.sleep(0.5)

bus = EventBus()