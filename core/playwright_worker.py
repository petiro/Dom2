import threading
import queue
import traceback
import logging

class PlaywrightWorker:
    def __init__(self, logger=None):
        self.logger = logger or logging.getLogger("PlaywrightWorker")
        self.q = queue.Queue()
        self.running = False
        self.thread = None
        self.executor = None

    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        self.logger.info("Playwright Worker avviato.")

    def stop(self):
        self.logger.info("Arresto Playwright Worker richiesto...")
        self.running = False
        self.q.put((None, None, None))
        if self.thread:
            self.thread.join(timeout=2)
        self.logger.info("Playwright Worker arrestato.")

    def submit(self, func, *args, **kwargs):
        self.q.put((func, args, kwargs))

    def is_alive(self):
        return self.thread and self.thread.is_alive()

    def _run(self):
        self.logger.info("Worker Loop Iniziato.")
        while self.running:
            try:
                task = self.q.get(timeout=1)
                func, args, kwargs = task
                if func is None:
                    break
                
                # 🔴 FIX WORKER: Isolamento totale del task. 
                # Se crasha, il worker logga l'errore ma SOPRAVVIVE e passa al task successivo.
                try:
                    func(*args, **kwargs)
                except Exception as e:
                    self.logger.error(f"❌ Worker Task Crash: {e}\n{traceback.format_exc()}")

                self.q.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                self.logger.error(f"Errore critico nella coda worker: {e}")
                
        self.logger.info("Worker Loop Terminato.")