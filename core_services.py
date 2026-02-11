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
        self._stop_event = None

    async def start_all(self):
        if self._stop_event is None:
            self._stop_event = asyncio.Event()
        tasks = [
            asyncio.create_task(self._guard_task("telegram", self.start_telegram())),
            asyncio.create_task(self._guard_task("browser", self.start_browser())),
            asyncio.create_task(self._guard_task("ai", self.ai_worker())),
        ]
        await asyncio.gather(*tasks)

    async def _guard_task(self, label, coro):
        try:
            await coro
        except Exception as exc:
            self.queue.put((label, f"Error: {exc}"))

    async def start_telegram(self):
        if TelegramClient is None or events is None:
            self.queue.put(("telegram", "Telethon not available"))
            return
        if not self.api_id or not self.api_hash:
            self.queue.put(("telegram", "API_ID/API_HASH missing"))
            return

        self.telegram = TelegramClient("dom2_session", self.api_id, self.api_hash)
        self.telegram.add_event_handler(self.on_message, events.NewMessage)
        await self.telegram.start()
        self.queue.put(("telegram", "✅ Telegram online"))
        await self.telegram.run_until_disconnected()

    async def on_message(self, event):
        self.queue.put(("telegram", event.raw_text or ""))

    async def start_browser(self):
        if async_playwright is None:
            self.queue.put(("browser", "Playwright not available"))
            return

        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=True)
        self.queue.put(("browser", "🌐 Browser started"))

    async def ai_worker(self):
        """Placeholder loop for future AI worker tasks."""
        while self._stop_event and not self._stop_event.is_set():
            await asyncio.sleep(1)

    def request_stop(self):
        if not self._stop_event:
            return
        if self.core and self.core.loop.is_running():
            self.core.loop.call_soon_threadsafe(self._stop_event.set)
        else:
            self._stop_event.set()
