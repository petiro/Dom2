import threading
import queue


class PlaywrightWorker:

    def __init__(self, logger):
        self.executor = None
        self.logger = logger
        self.queue = queue.Queue()
        self.running = True

        self.thread = threading.Thread(
            target=self._loop,
            daemon=True
        )
        self.thread.start()

    def set_executor(self, executor):
        """Wire the executor into the worker."""
        self.executor = executor

    def submit(self, fn, *args, **kwargs):
        self.queue.put((fn, args, kwargs))

    def _loop(self):
        while self.running:
            try:
                fn, args, kwargs = self.queue.get(timeout=1)
            except queue.Empty:
                continue
            try:
                fn(*args, **kwargs)
            except Exception as e:
                self.logger.error(f"[Worker] {e}")
            finally:
                self.queue.task_done()

    def stop(self):
        self.running = False
