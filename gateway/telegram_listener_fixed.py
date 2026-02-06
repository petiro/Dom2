from telethon import TelegramClient, events
import asyncio
import os
import yaml


def start_telegram_listener():
    """
    Validate Telegram credentials at startup.
    The actual connection is handled via the UI TelegramTab connect button.
    """
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_path = os.path.join(base_dir, "config", "config.yaml")

    if not os.path.exists(config_path):
        raise RuntimeError("config.yaml non trovato")

    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}

    telegram_cfg = config.get("telegram", {})
    api_id = telegram_cfg.get("api_id")
    api_hash = telegram_cfg.get("api_hash")

    if not api_id or not api_hash:
        raise RuntimeError("Telegram api_id/api_hash non configurati in config.yaml - configura dal tab Telegram nella UI")

    print(f"Telegram listener pronto (api_id={api_id})")


class TelegramListener:
    def __init__(self, api_id, api_hash, agent, parser, logger):
        self.client = TelegramClient('session_name', api_id, api_hash)
        self.agent = agent
        self.parser = parser
        self.logger = logger

    async def start(self):
        @self.client.on(events.NewMessage)
        async def handler(event):
            # Check if agent is busy (if agent supports state checking)
            if self.agent and hasattr(self.agent, 'state'):
                if self.agent.state != "IDLE":
                    self.logger.info("Agent busy, skipping signal.")
                    return

            text = event.message.message
            signal = self.parser.parse_signal(text)

            if signal:
                self.logger.info(f"New Signal: {signal}")
                if self.agent and hasattr(self.agent, 'handle_signal'):
                    asyncio.create_task(self.agent.handle_signal(signal))
                else:
                    self.logger.info(f"Signal received but no agent handler: {signal}")

        await self.client.start()
        self.logger.info("Telegram listener started successfully")
        await self.client.run_until_disconnected()
