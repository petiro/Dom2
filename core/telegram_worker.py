import os
import asyncio
import logging
from queue import Full
from PySide6.QtCore import QThread, Signal

# Configurazione Logger
logger = logging.getLogger("telegram_worker")

try:
    from telethon import TelegramClient, events
    TELETHON_AVAILABLE = True
except ImportError:
    TELETHON_AVAILABLE = False
    logger.error("Telethon non installato! Installa con: pip install telethon")

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

class TelegramWorker(QThread):
    """
    Worker isolato per Telegram.
    Gestisce la connessione in un thread separato con il proprio Event Loop asyncio.
    NON blocca la GUI e NON richiede stdin (dopo il primo login).
    """
    message_received = Signal(str)      # Segnale per la UI
    status_changed = Signal(str)        # Cambio stato (Connesso/Disconnesso)
    error_occurred = Signal(str)        # Errori critici (es. Login mancante)
    chats_loaded = Signal(list)         # Lista chat per la selezione

    def __init__(self, config, message_queue=None):
        super().__init__()
        self.api_id = int(config.get('api_id', 0))
        self.api_hash = config.get('api_hash', '')
        self.selected_chats = config.get('selected_chats', [])
        self.message_queue = message_queue  # Coda thread-safe per il Controller
        
        self.client = None
        self.loop = None
        self.keep_alive_task = None
        
        # Path sicuro per la sessione (compatibile con PyInstaller)
        self._data_dir = os.path.join(_BASE_DIR, "data")
        os.makedirs(self._data_dir, exist_ok=True)

    def run(self):
        """Entry point del QThread. Crea e gestisce il loop asyncio."""
        if not TELETHON_AVAILABLE:
            self.error_occurred.emit("Libreria Telethon mancante")
            return

        # 1. Creazione Loop Isolato
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        
        try:
            # 2. Avvio task principale
            self.loop.run_until_complete(self._main())
        except Exception as e:
            logger.error(f"Errore critico nel thread Telegram: {e}")
            self.error_occurred.emit(f"Crash Telegram: {str(e)}")
        finally:
            # 3. Pulizia risorse alla chiusura
            try:
                if not self.loop.is_closed():
                    pending = asyncio.all_tasks(self.loop)
                    for task in pending:
                        task.cancel()
                    # Attende la cancellazione dei task pendenti
                    self.loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                    self.loop.close()
            except Exception as e:
                logger.error(f"Errore chiusura loop: {e}")

    async def _main(self):
        """Logica asincrona principale."""
        # Nome sessione fisso per persistenza
        session_path = os.path.join(self._data_dir, "session_v4")
        
        self.client = TelegramClient(session_path, self.api_id, self.api_hash)
        
        self.status_changed.emit("Connessione in corso...")
        
        # --- FIX CRITICO: CONNESSIONE MANUALE ---
        # NON usare await self.client.start() qui, perché cerca stdin!
        try:
            await self.client.connect()
        except Exception as e:
            self.error_occurred.emit(f"Errore connessione: {e}")
            return

        # Controllo autorizzazione
        if not await self.client.is_user_authorized():
            self.status_changed.emit("Richiesto Login")
            # Emettiamo errore specifico per dire all'utente di usare la console
            self.error_occurred.emit("SESSIONE MANCANTE: Esegui il primo avvio con --console per fare il login.")
            return

        self.status_changed.emit("Connesso")
        logger.info("Telegram Client connesso e autorizzato.")

        # Carica lista chat (opzionale, utile per debug)
        try:
            dialogs = await self.client.get_dialogs(limit=30)
            chat_list = [{'id': d.id, 'name': d.name} for d in dialogs if d.is_channel or d.is_group]
            self.chats_loaded.emit(chat_list)
        except Exception as e:
            logger.warning(f"Impossibile caricare lista chat: {e}")

        # Handler messaggi
        @self.client.on(events.NewMessage(chats=self.selected_chats if self.selected_chats else None))
        async def handler(event):
            text = event.message.message
            
            # Log e invio alla UI
            logger.info(f"Messaggio ricevuto: {text[:20]}...")
            self.message_received.emit(text)
            
            # Invio alla coda sicura per il Controller
            if self.message_queue:
                try:
                    # Mettiamo solo il testo raw per il parser
                    self.message_queue.put_nowait(text)
                except Full:
                    pass

        # Task Keep-Alive (Previene disconnessioni silenziose)
        self.keep_alive_task = self.loop.create_task(self._keep_alive())
        
        # Blocca il thread finché non ci disconnettiamo
        await self.client.run_until_disconnected()

    async def _keep_alive(self):
        """Ping periodico per mantenere la connessione attiva."""
        while True:
            try:
                if not self.client.is_connected():
                    await self.client.connect()
                # Un semplice get_me tiene viva la sessione
                await self.client.get_me()
            except Exception:
                pass
            await asyncio.sleep(60)

    def stop(self):
        """Metodo thread-safe per fermare il worker dalla UI."""
        self.status_changed.emit("Disconnessione...")
        if self.client and self.loop and self.loop.is_running():
            # Inietta la disconnessione nel loop del thread
            asyncio.run_coroutine_threadsafe(self.client.disconnect(), self.loop)
        
        self.quit()
        self.wait(3000)  # Aspetta max 3 secondi
