import threading
import queue
import logging
import time
from typing import Callable, Dict, List, Any

class EventBus:
    def __init__(self):
        # 🔴 FIX CI: TYPING SPECIFICO (str invece di Any per gli eventi)
        self._subscribers: Dict[str, List[Callable]] = {}
        self._queue: queue.Queue = queue.Queue()
        self._running: bool = False
        self._dispatcher: threading.Thread | None = None
        self.logger = logging.getLogger("EventBus")

    # 🔴 FIX CI: RETURN TYPE NONE E TYPE HINT STR
    def subscribe(self, event: str, callback: Callable) -> None:
        self._subscribers.setdefault(event, []).append(callback)

    # 🔴 FIX CI: RETURN TYPE NONE E TYPE HINT STR
    def emit(self, event: str, payload: dict | None = None) -> None:
        if not self._running:
            return

        if self._queue.qsize() > 5000:
            self.logger.warning("⚠️ EventBus overflow. Evento scartato.")
            return

        self._queue.put((event, payload or {}))

    def start(self):
        if self._running: return
        self._running = True
        self._dispatcher = threading.Thread(target=self._dispatch_loop, daemon=True, name="EventBusDispatcher")
        self._dispatcher.start()
        self.logger.info("EventBus avviato.")

    def stop(self):
        self._running = False
        if self._dispatcher: self._dispatcher.join(timeout=3)

    def _dispatch_loop(self):
        while self._running or not self._queue.empty():
            try:
                event, payload = self._queue.get(timeout=0.5)
                callbacks = self._subscribers.get(event, [])
                for cb in callbacks:
                    try: cb(payload)
                    except Exception as e: self.logger.exception(f"🔥 Callback crash su evento {event}: {e}")
                self._queue.task_done()
            except queue.Empty: continue
            except Exception:
                self.logger.exception("🔥 EventBus dispatcher crash evitato")
                time.sleep(0.5)

bus = EventBus()
