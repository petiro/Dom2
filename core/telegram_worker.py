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

    def run(self):
        asyncio.run(self._start_client())

    async def _start_client(self):
        self.client = TelegramClient('session_v4', self.api_id, self.api_hash)
        await self.client.start()  # User client start

        @self.client.on(events.NewMessage(chats=self.selected_chats))
        async def handler(event):
            self.message_received.emit(event.raw_text)

        await self.client.run_until_disconnected()

    def stop(self):
        self._running = False
        if self.client:
            self.client.disconnect()
