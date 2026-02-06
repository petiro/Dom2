from telethon import TelegramClient, events
import asyncio

class TelegramListener:
    def __init__(self, api_id, api_hash, agent, parser, logger):
        self.client = TelegramClient('session_name', api_id, api_hash)
        self.agent = agent
        self.parser = parser
        self.logger = logger

    async def start(self):
        @self.client.on(events.NewMessage)
        async def handler(event):
            # Import AgentState here to avoid circular dependencies
            from main import AgentState
            
            # Rule: if agent is busy, ignore and discard
            if self.agent.state != AgentState.IDLE:
                self.logger.info("Agent busy, skipping signal.")
                return

            text = event.message.message
            signal = self.parser.parse_signal(text)
            
            if signal:
                self.logger.info(f"New Signal: {signal}")
                # Pass command to agent
                asyncio.create_task(self.agent.handle_signal(signal))

        await self.client.start()
        self.logger.info("Telegram listener started successfully")
        await self.client.run_until_disconnected()
