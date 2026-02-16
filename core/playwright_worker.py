import threading
import queue


class PlaywrightWorker:

    def __init__(self, executor, logger):
        self.executor = executor
        self.logger = logger
        self.queue = queue.Queue()
        self.running = True

        self.thread = threading.Thread(
            target=self._loop,
            daemon=True
        )
        self.thread.start()

    def submit(self, fn, *args, **kwargs):
        self.queue.put((fn, args, kwargs))

    def _loop(self):
        while self.running:
            fn, args, kwargs = self.queue.get()
            try:
                fn(*args, **kwargs)
            except Exception as e:
                self.logger.error(f"[Worker] {e}")

    def stop(self):
        self.running = False
