import threading
import queue
import logging


class EventBus:
    _instance = None
    _instance_lock = threading.Lock()

    def __new__(cls):
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = super(EventBus, cls).__new__(cls)
                cls._instance.listeners = {}
                cls._instance.event_queue = queue.Queue()
                cls._instance.logger = logging.getLogger("SuperAgent")
                cls._instance.running = True

                cls._instance.dispatcher_thread = threading.Thread(
                    target=cls._instance._dispatch_loop,
                    daemon=True,
                    name="EventBus_Dispatcher"
                )
                cls._instance.dispatcher_thread.start()

        return cls._instance

    def subscribe(self, event_type, callback):
        with self._instance_lock:
            if event_type not in self.listeners:
                self.listeners[event_type] = []
            self.listeners[event_type].append(callback)

    def emit(self, event_type, data=None):
        if not self.running:
            return
        self.event_queue.put((event_type, data))

    def _dispatch_loop(self):
        while self.running:
            try:
                event_type, data = self.event_queue.get(timeout=1)

                with self._instance_lock:
                    callbacks = list(self.listeners.get(event_type, []))

                for callback in callbacks:
                    try:
                        callback(data)
                    except Exception as e:
                        self.logger.error(
                            f"EventBus Dispatch Error [{event_type}]: {e}"
                        )

                self.event_queue.task_done()

            except queue.Empty:
                continue
            except Exception as e:
                self.logger.critical(f"EventBus Loop Critical Error: {e}")

    def stop(self):
        self.running = False
        try:
            self.dispatcher_thread.join(timeout=2)
        except Exception:
            pass


# Singleton
bus = EventBus()
