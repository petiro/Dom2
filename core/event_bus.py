import logging
import traceback
from concurrent.futures import ThreadPoolExecutor

class EventBus:
    def __init__(self):
        self.subscribers = {}
        self.logger = logging.getLogger("EventBus")
        # 🔴 FIX: Pool limitato a 5 thread. Niente flood di RAM sulla VPS!
        self.executor = ThreadPoolExecutor(max_workers=5)

    def subscribe(self, event_type, callback):
        if event_type not in self.subscribers:
            self.subscribers[event_type] = []
        self.subscribers[event_type].append(callback)

    def emit(self, event_type, payload):
        if event_type in self.subscribers:
            for callback in self.subscribers[event_type]:
                # 🔴 FIX: Accoda il task al pool invece di creare thread infiniti
                self.executor.submit(self._safe_execute, callback, payload, event_type)

    def _safe_execute(self, callback, payload, event_type):
        """Esecutore isolato per proteggere il ThreadPool"""
        try:
            callback(payload)
        except Exception as e:
            self.logger.error(f"❌ Crash nel Subscriber '{callback.__name__}' per evento '{event_type}': {e}\n{traceback.format_exc()}")

    def start(self):
        self.logger.info("EventBus avviato. ThreadPool pronto.")

    def stop(self):
        self.executor.shutdown(wait=False)
        self.logger.info("EventBus fermato.")

bus = EventBus()