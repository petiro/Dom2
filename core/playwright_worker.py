import threading
import queue
import time

class PlaywrightWorker:
    def __init__(self, logger):
        self.logger = logger
        self.queue = queue.Queue()
        self.running = False
        self.thread = None
        self.executor = None

    def start(self):
        if self.running:
            return

        self.running = True
        self.thread = threading.Thread(target=self._loop, daemon=True, name="PW_Worker")
        self.thread.start()
        self.logger.info("Playwright Worker avviato.")

    def stop(self):
        self.logger.info("Arresto Playwright Worker richiesto...")
        self.running = False

        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=3.0)

        if self.executor:
            try:
                self.executor.close()
            except Exception as e:
                self.logger.error("Errore chiusura executor: %s", e)

        self.logger.info("Playwright Worker arrestato.")

    def submit(self, fn, *args, **kwargs):
        if not self.running:
            self.logger.warning("Tentativo di submit su worker spento. Ignorato.")
            return False

        if self.queue.qsize() > 100:
            self.logger.warning("Worker Queue satura! Task droppato.")
            return False

        self.queue.put((fn, args, kwargs))
        return True

    def _loop(self):
        self.logger.info("Worker Loop Iniziato.")

        while self.running:
            try:
                fn, args, kwargs = self.queue.get(timeout=1.0)
            except queue.Empty:
                continue

            try:
                start_time = time.time()
                fn(*args, **kwargs)
                exec_time = time.time() - start_time

                if exec_time > 30.0:
                    self.logger.warning("⚠️ Task lento (%s): %.2fs", getattr(fn, '__name__', 'unknown'), exec_time)

            except Exception as e:
                self.logger.exception("❌ Errore critico nel task worker: %s", e)
            finally:
                self.queue.task_done()

        self.logger.info("Worker Loop Terminato.")