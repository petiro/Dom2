import os
import asyncio
import logging
from queue import Full
from pathlib import Path

try:
    from PySide6.QtCore import QThread, Signal
except ImportError:
    class QThread: pass
    class Signal:
        def __init__(self, *args, **kwargs): pass
        def emit(self, *args, **kwargs): pass

from telethon import TelegramClient, events
from telethon.sessions import StringSession

logger = logging.getLogger("SuperAgent")

class TelegramWorker(QThread):
    message_received = Signal(str)
    status_changed = Signal(str)
    error_occurred = Signal(str)

    def __init__(self, config, message_queue=None):
        super().__init__()
        logger.info("🛠️ Inizializzazione TelegramWorker (Secure Mode)...")
        self.message_queue = message_queue
        self.client = None
        self.loop = None
        self.keep_alive_task = None

        try:
            raw_id = config.get('telegram', {}).get('api_id', 0)
            self.api_id = int(raw_id) if raw_id else 0
        except (ValueError, TypeError):
            self.api_id = 0

        self.api_hash = config.get('telegram', {}).get('api_hash', '')

        raw_chats = config.get('selected_chats', [])
        if isinstance(raw_chats, str):
            self.selected_chats = [raw_chats]
        elif isinstance(raw_chats, list):
            self.selected_chats = raw_chats
        else:
            self.selected_chats = []

    def run(self):
        if not self.api_id or not self.api_hash:
            logger.critical("⛔ Impossibile avviare: Credenziali Telegram mancanti nel config")
            self.error_occurred.emit("CONFIG ERROR: API ID/HASH mancanti")
            return

        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        try:
            self.loop.run_until_complete(self._main())
        except Exception as e:
            logger.critical("🔥 CRASH LOOP TELEGRAM: %s", e, exc_info=True)
            self.error_occurred.emit(f"CRITICAL LOOP ERROR: {str(e)}")
        finally:
            pending = asyncio.all_tasks(loop=self.loop)
            for task in pending: task.cancel()
            if not self.loop.is_closed():
                self.loop.close()
            logger.info("🛑 TelegramWorker Terminato Pulito")

    async def _main(self):
        save_dir = os.path.join(str(Path.home()), ".superagent_data")
        os.makedirs(save_dir, exist_ok=True)
        session_file = os.path.join(save_dir, "telegram_session.dat")

        session_string = ""
        if os.path.exists(session_file):
            with open(session_file, "r", encoding="utf-8") as f:
                session_string = f.read().strip()

        self.client = TelegramClient(
            StringSession(session_string), 
            self.api_id, 
            self.api_hash,
            device_model="SuperAgent",
            system_version="Production",
            app_version="8.5"
        )

        self.status_changed.emit("Connessione in corso...")
        logger.info("📡 Tentativo di connessione a Telegram...")
        try:
            await self.client.connect()
        except Exception as e:
            logger.error("❌ Connessione fallita: %s", e)
            self.error_occurred.emit(f"CONNECTION FAILED: {str(e)}")
            return

        if not await self.client.is_user_authorized():
            logger.warning("⚠️ Sessione Telegram vuota o scaduta. Incolla la StringSession generata.")
            self.status_changed.emit("Richiesto Login")
            self.error_occurred.emit("SESSION_MISSING: Login richiesto dalla UI.")
            await self.client.disconnect()
            return
        else:
            current_session = self.client.session.save()
            
            # 🔴 FIX HEDGE-GRADE: Scrittura Atomica della sessione
            tmp_file = session_file + ".tmp"
            with open(tmp_file, "w", encoding="utf-8") as f:
                f.write(current_session)
            os.replace(tmp_file, session_file)
            
            logger.info("✅ Telegram Connesso! Vault Session Atomica in uso.")
            self.status_changed.emit("Connesso")

        @self.client.on(events.NewMessage(chats=self.selected_chats if self.selected_chats else None))
        async def handler(event):
            msg_text = event.raw_text
            logger.info("📩 Messaggio Ricevuto: %s...", msg_text[:80].replace("\n", " "))
            if self.message_queue:
                try:
                    self.message_queue.put_nowait(msg_text)
                except Full:
                    pass
            else:
                self.message_received.emit(msg_text)

        async def keep_alive():
            while True:
                try:
                    if not self.client.is_connected():
                        await self.client.connect()
                    await self.client.get_me()
                except asyncio.CancelledError:
                    break
                except Exception:
                    pass
                await asyncio.sleep(60)

        self.keep_alive_task = self.loop.create_task(keep_alive())

        try:
            await self.client.run_until_disconnected()
        except asyncio.CancelledError:
            pass
        finally:
            if self.keep_alive_task and not self.keep_alive_task.done():
                self.keep_alive_task.cancel()

    def stop(self):
        logger.info("🛑 Richiesta di stop ricevuta...")
        if self.loop and self.loop.is_running():
            async def shutdown():
                if self.keep_alive_task:
                    self.keep_alive_task.cancel()
                if self.client:
                    await self.client.disconnect()
            asyncio.run_coroutine_threadsafe(shutdown(), self.loop)
        self.quit()
        self.wait(2000)