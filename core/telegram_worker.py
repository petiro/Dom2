import os
from queue import Full
from PySide6.QtCore import QThread, Signal
import asyncio

try:
    from telethon import TelegramClient, events
    TELETHON_AVAILABLE = True
except ImportError:
    TELETHON_AVAILABLE = False

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

class TelegramWorker(QThread):
    chats_loaded = Signal(list)
    message_received = Signal(str)

    def __init__(self, config, message_queue=None):
        super().__init__()
        self.api_id = int(config.get('api_id', 0))
        self.api_hash = config.get('api_hash', '')
        self.selected_chats = config.get('selected_chats', [])
        self.client = None
        self.loop = None
        self.message_queue = message_queue
        self.keep_alive_task = None
        
        # Absolute session path for PyInstaller compatibility
        self._data_dir = os.path.join(_BASE_DIR, "data")
        os.makedirs(self._data_dir, exist_ok=True)

    def run(self):
        if not TELETHON_AVAILABLE:
            return
        # Creiamo un nuovo loop per questo thread (evita l'errore 'Dummy-1')
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        try:
            self.loop.run_until_complete(self._main())
        finally:
            if not self.loop.is_closed():
                self.loop.close()

    def stop(self):
        """Ferma il worker in modo sicuro e thread-safe."""
        if self.client and self.loop and not self.loop.is_closed():
            try:
                # 1. Cancella il task di keep_alive se esiste
                if self.keep_alive_task and not self.keep_alive_task.done():
                    future = asyncio.run_coroutine_threadsafe(
                        self._cancel_keep_alive(), self.loop
                    )
                    future.result(timeout=5)
                
                # 2. Disconnetti il client
                future = asyncio.run_coroutine_threadsafe(
                    self.client.disconnect(), self.loop
                )
                future.result(timeout=5)
            except Exception:
                pass
        self.quit()
        self.wait(5000)

    async def _cancel_keep_alive(self):
        """Cancella e attende il task keep_alive per evitare warning."""
        if self.keep_alive_task and not self.keep_alive_task.done():
            self.keep_alive_task.cancel()
            try:
                await self.keep_alive_task
            except asyncio.CancelledError:
                pass

    async def _main(self):
        session_path = os.path.join(self._data_dir, "session_v4")
        self.client = TelegramClient(session_path, self.api_id, self.api_hash)
        await self.client.start()

        @self.client.on(events.NewMessage(chats=self.selected_chats))
        async def handler(event):
            # Se la coda è disponibile, usala (thread-safe)
            if self.message_queue is not None:
                try:
                    self.message_queue.put_nowait(event.raw_text)
                except Full:
                    pass
            else:
                # Altrimenti usa i segnali Qt standard
                self.message_received.emit(event.raw_text)

        # KEEP-ALIVE LOOP (Cruciale per connessioni lunghe)
        async def keep_alive():
            while True:
                try:
                    if not self.client.is_connected():
                        await self.client.connect()
                    await self.client.get_me()
                except Exception:
                    pass
                await asyncio.sleep(60)

        # Avvia il task e salvalo in self per poterlo cancellare dopo
        self.keep_alive_task = self.loop.create_task(keep_alive())
        
        try:
            await self.client.run_until_disconnected()
        finally:
            # Pulisci il task anche se Telegram si disconnette per errore
            await self._cancel_keep_alive()
