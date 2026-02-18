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
        """Avvia il thread del worker se non è già attivo."""
        if self.running:
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._loop, daemon=True, name="PW_Worker")
        self.thread.start()
        self.logger.info("Playwright Worker avviato.")

    def stop(self):
        """Ferma il worker, attende il thread e chiude l'executor."""
        self.logger.info("Arresto Playwright Worker richiesto...")
        self.running = False
        
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=3.0)
        
        # Chiusura sicura dell'executor (Browser)
        if self.executor:
            try:
                # Tentativo chiusura con timeout implicito (non bloccante)
                self.executor.close()
            except Exception as e:
                self.logger.error(f"Errore chiusura executor: {e}")

        self.logger.info("Playwright Worker arrestato.")

    def submit(self, fn, *args, **kwargs):
        """
        Invia un task alla coda. 
        Ritorna True se accodato, False se il worker è fermo.
        """
        if not self.running:
            self.logger.warning("Tentativo di submit su worker spento. Ignorato.")
            return False
        
        # FIX: Check anti-overflow (opzionale ma consigliato per H24)
        if self.queue.qsize() > 100:
            self.logger.warning("Worker Queue satura! Task droppato.")
            return False

        self.queue.put((fn, args, kwargs))
        return True

    def _loop(self):
        """Ciclo principale di elaborazione task."""
        self.logger.info("Worker Loop Iniziato.")
        
        while self.running:
            try:
                # Timeout necessario per controllare self.running periodicamente
                fn, args, kwargs = self.queue.get(timeout=1.0)
            except queue.Empty:
                continue

            try:
                # Esecuzione blindata
                # self.logger.debug(f"Esecuzione task: {fn.__name__}") # Debug opzionale
                start_time = time.time()
                
                fn(*args, **kwargs)
                
                exec_time = time.time() - start_time
                if exec_time > 30.0:
                    self.logger.warning(f"⚠️ Task lento ({fn.__name__}): {exec_time:.2f}s")

            except Exception as e:
                self.logger.exception(f"❌ Errore critico nel task worker: {e}")
            finally:
                self.queue.task_done()
        
        self.logger.info("Worker Loop Terminato.")