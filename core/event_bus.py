import logging
import traceback

class EventBus:
    def __init__(self):
        self.subscribers = {}
        self.logger = logging.getLogger("EventBus")

    def subscribe(self, event_type, callback):
        if event_type not in self.subscribers:
            self.subscribers[event_type] = []
        self.subscribers[event_type].append(callback)

    def emit(self, event_type, payload):
        if event_type in self.subscribers:
            for callback in self.subscribers[event_type]:
                # 🔴 FIX EVENTBUS: Un subscriber guasto non bloccherà gli altri
                try:
                    callback(payload)
                except Exception as e:
                    self.logger.error(f"❌ Crash nel Subscriber '{callback.__name__}' per evento '{event_type}': {e}\n{traceback.format_exc()}")
                    continue  # Fondamentale: passa al prossimo senza uccidere il ciclo

    def start(self):
        self.logger.info("EventBus avviato.")

    def stop(self):
        self.logger.info("EventBus fermato.")

bus = EventBus()