import os
from queue import Full
from PySide6.QtCore import QThread, Signal
import asyncio
import logging

# Logger specifico per questo modulo
logger = logging.getLogger("telegram_worker")

try:
    from telethon import TelegramClient, events
    TELETHON_AVAILABLE = True
except ImportError:
    TELETHON_AVAILABLE = False
    logger.error("Telethon non installato!")

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
        
        # Absolute session path
        self._data_dir = os.path.join(_BASE_DIR, "data")
        os.makedirs(self._data_dir, exist_ok=True)

    def run(self):
        if not TELETHON_AVAILABLE:
            return
        
        # Nuovo loop per il thread QThread
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        
        try:
            self.loop.run_until_complete(self._main())
        except Exception as e:
            logger.error(f"Errore nel loop Telegram: {e}")
        finally:
            # Pulizia corretta del loop
            try:
                if not self.loop.is_closed():
                    pending = asyncio.all_tasks(self.loop)
                    for task in pending:
                        task.cancel()
                    self.loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                    self.loop.close()
            except Exception as e:
                logger.error(f"Errore chiusura loop: {e}")

    async def _main(self):
        session_path = os.path.join(self._data_dir, 'anon')
        self.client = TelegramClient(session_path, self.api_id, self.api_hash)
        
        await self.client.start()
        
        # Carica chat
        dialogs = await self.client.get_dialogs(limit=50)
        chat_list = [{'id': d.id, 'name': d.name} for d in dialogs if d.is_channel or d.is_group]
        self.chats_loaded.emit(chat_list)

        # Ascolta nuovi messaggi
        @self.client.on(events.NewMessage(chats=self.selected_chats))
        async def handler(event):
            text = event.message.message
            sender = await event.get_sender()
            sender_name = sender.title if hasattr(sender, 'title') else 'Unknown'
            
            logger.info(f"Messaggio da {sender_name}: {text[:30]}...")
            
            self.message_received.emit(f"[{sender_name}] {text}")
            
            if self.message_queue:
                try:
                    self.message_queue.put_nowait(("telegram", text))
                except Full:
                    pass

        # Keep alive
        self.keep_alive_task = asyncio.create_task(self._keep_alive())
        await self.client.run_until_disconnected()

    async def _keep_alive(self):
        while True:
            await asyncio.sleep(60)
            # Placeholder per evitare che il loop muoia se non arrivano messaggi

    def stop(self):
        """Ferma il worker in sicurezza"""
        if self.loop and self.loop.is_running():
            asyncio.run_coroutine_threadsafe(self._stop_client(), self.loop)
        
        self.wait(2000)
        if self.isRunning():
            self.terminate()

    async def _stop_client(self):
        if self.client:
            await self.client.disconnect()
