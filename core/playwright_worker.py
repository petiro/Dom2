import threading
import queue
import logging
import time

class PlaywrightWorker:
    def __init__(self, logger):
        self.logger = logger
        self.queue = queue.Queue()
        self.running = False
        self.thread = None
        self.executor = None 

    def start(self):
        if self.running: return
        self.running = True
        self.thread = threading.Thread(target=self._loop, daemon=True, name="PW_Worker")
        self.thread.start()

    def stop(self):
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2.0)
        if self.executor:
            try: self.executor.close()
            except: pass

    def submit(self, fn, *args, **kwargs):
        if not self.running: return
        self.queue.put((fn, args, kwargs))

    def _loop(self):
        self.logger.info("Playwright Worker started.")
        while self.running:
            try:
                item = self.queue.get(timeout=1.0)
            except queue.Empty:
                continue

            try:
                fn, args, kwargs = item
                fn(*args, **kwargs)
            except Exception as e:
                self.logger.error(f"[Worker Error] {e}", exc_info=True)
            finally:
                self.queue.task_done()
        
        self.logger.info("Playwright Worker stopped.")