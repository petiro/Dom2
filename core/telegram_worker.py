from telethon import TelegramClient, events
from PySide6.QtCore import QThread, Signal
import asyncio

class TelegramWorker(QThread):
    chats_loaded = Signal(list)
    message_received = Signal(str)

    def __init__(self, config):
        super().__init__()
        self.api_id = int(config.get('api_id', 0))
        self.api_hash = config.get('api_hash', '')
        self.selected_chats = config.get('selected_chats', [])
        self.client = None
        self.loop = asyncio.new_event_loop()

    def run(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self._main())

    def stop(self):
        if self.client:
            self.loop.call_soon_threadsafe(self.client.disconnect)
        self.quit()
        self.wait()

    async def _main(self):
        self.client = TelegramClient('session_v4', self.api_id, self.api_hash)
        await self.client.start()

        @self.client.on(events.NewMessage(chats=self.selected_chats))
        async def handler(event):
            self.message_received.emit(event.raw_text)

        # KEEP-ALIVE LOOP (Cruciale)
        async def keep_alive():
            while True:
                try:
                    if not self.client.is_connected():
                        await self.client.connect()
                    await self.client.get_me()
                except Exception:
                    pass
                await asyncio.sleep(60)

        self.loop.create_task(keep_alive())
        await self.client.run_until_disconnected()
