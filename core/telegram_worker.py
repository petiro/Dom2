import asyncio
from PySide6.QtCore import QThread, Signal
from telethon import TelegramClient, events


class TelegramWorker(QThread):
    message_received = Signal(str)
    chats_loaded = Signal(list)

    def __init__(self, config):
        super().__init__()
        self.api_id = config.get('api_id')
        self.api_hash = config.get('api_hash')
        self.bot_token = config.get('bot_token')
        self.selected_chats = config.get('selected_chats', [])
        self.client = None
        self._running = True
        self.loop = asyncio.new_event_loop()

    def run(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self._main())

    async def _main(self):
        self.client = TelegramClient('session_v4', self.api_id, self.api_hash)
        await self.client.start()

        @self.client.on(events.NewMessage(chats=self.selected_chats))
        async def handler(event):
            self.message_received.emit(event.raw_text)

        # Keep-alive task to prevent silent disconnections
        async def keep_alive():
            while True:
                try:
                    if not self.client.is_connected():
                        await self.client.connect()
                    await self.client.get_me()  # Ping
                except Exception:
                    pass
                await asyncio.sleep(60)

        self.loop.create_task(keep_alive())
        await self.client.run_until_disconnected()

    def stop(self):
        self._running = False
        if self.client:
            self.client.disconnect()
