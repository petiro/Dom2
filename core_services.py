import asyncio

try:
    from telethon import TelegramClient, events
except ImportError:  # pragma: no cover - optional dependency
    TelegramClient = None
    events = None

try:
    from playwright.async_api import async_playwright
except ImportError:  # pragma: no cover - optional dependency
    async_playwright = None


class CoreServices:
    def __init__(self, core, queue, api_id=None, api_hash=None):
        self.core = core
        self.queue = queue
        self.api_id = api_id
        self.api_hash = api_hash
        self.telegram = None
        self.browser = None
        self.playwright = None

    async def start_all(self):
        await asyncio.gather(
            self.start_telegram(),
            self.start_browser(),
            self.ai_worker(),
            return_exceptions=True,
        )

    async def start_telegram(self):
        if TelegramClient is None or events is None:
            self.queue.put(("telegram", "Telethon non disponibile"))
            return
        if not self.api_id or not self.api_hash:
            self.queue.put(("telegram", "API_ID/API_HASH mancanti"))
            return

        self.telegram = TelegramClient("dom2_session", self.api_id, self.api_hash)
        self.telegram.add_event_handler(self.on_message, events.NewMessage)
        await self.telegram.start()
        self.queue.put(("telegram", "✅ Telegram Online"))
        await self.telegram.run_until_disconnected()

    async def on_message(self, event):
        self.queue.put(("telegram", event.raw_text or ""))

    async def start_browser(self):
        if async_playwright is None:
            self.queue.put(("browser", "Playwright non disponibile"))
            return

        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=True)
        self.queue.put(("browser", "🌐 Browser avviato"))

    async def ai_worker(self):
        """Placeholder loop for future AI worker tasks."""
        while True:
            await asyncio.sleep(1)
