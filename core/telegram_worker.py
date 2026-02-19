import os
import asyncio
import logging
from queue import Full

# 🔴 FIX PYSIDE6 IN GITHUB ACTIONS (Nessuna GUI sul server CI)
try:
    from PySide6.QtCore import QThread, Signal
except ImportError:
    class QThread: pass
    class Signal:
        def __init__(self, *args, **kwargs): pass
        def emit(self, *args, **kwargs): pass

from telethon import TelegramClient, events

logger = logging.getLogger("SuperAgent")

class TelegramWorker(QThread):
    message_received = Signal(str)
    status_changed = Signal(str)
    error_occurred = Signal(str)

    def __init__(self, config, message_queue=None):
        super().__init__()
        logger.info("🛠️ Inizializzazione TelegramWorker...")
        self.message_queue = message_queue
        self.client = None
        self.loop = None
        self.keep_alive_task = None

        try:
            raw_id = config.get('api_id', 0)
            self.api_id = int(raw_id) if raw_id else 0
        except (ValueError, TypeError):
            self.api_id = 0

        if not self.api_id:
            self.api_id = None
            logger.error("❌ Configurazione: API ID non valido o mancante")

        self.api_hash = config.get('api_hash', '')

        raw_chats = config.get('selected_chats', [])
        if isinstance(raw_chats, str):
            self.selected_chats = [raw_chats]
        elif isinstance(raw_chats, list):
            self.selected_chats = raw_chats
        else:
            self.selected_chats = []

        logger.debug("📋 Chat selezionate: %s", self.selected_chats)

        _base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self._data_dir = os.path.join(_base, "data")
        os.makedirs(self._data_dir, exist_ok=True)

    def run(self):
        if not self.api_id or not self.api_hash:
            logger.critical("⛔ Impossibile avviare: Credenziali mancanti")
            self.error_occurred.emit("CONFIG ERROR: API ID o HASH mancanti/invalidi")
            return

        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        try:
            self.loop.run_until_complete(self._main())
        except Exception as e:
            logger.critical("🔥 CRASH LOOP TELEGRAM: %s", e, exc_info=True)
            self.error_occurred.emit(f"CRITICAL LOOP ERROR: {str(e)}")
        finally:
            if not self.loop.is_closed():
                self.loop.close()
            logger.info("🛑 TelegramWorker Terminato")

    async def _main(self):
        session_path = os.path.join(self._data_dir, "session_v4")
        self.client = TelegramClient(session_path, self.api_id, self.api_hash)

        self.status_changed.emit("Connessione in corso...")
        logger.info("📡 Tentativo di connessione a Telegram...")
        try:
            await self.client.connect()
        except Exception as e:
            logger.error("❌ Connessione fallita: %s", e)
            self.error_occurred.emit(f"CONNECTION FAILED: {str(e)}")
            return

        if not await self.client.is_user_authorized():
            logger.warning("⚠️ Sessione Telegram scaduta o mancante. Richiesto Login Manuale.")
            self.status_changed.emit("Richiesto Login")
            self.error_occurred.emit("SESSION_MISSING: Esegui l'app con --console per il primo login.")
            await self.client.disconnect()
            return

        logger.info("✅ Telegram Connesso! User ID valido.")
        self.status_changed.emit("Connesso")

        @self.client.on(events.NewMessage(chats=self.selected_chats if self.selected_chats else None))
        async def handler(event):
            msg_text = event.raw_text
            logger.info("📩 Messaggio Ricevuto: %s...", msg_text[:100])

            if self.message_queue:
                try:
                    self.message_queue.put_nowait(msg_text)
                except Full:
                    logger.warning("⚠️ Coda messaggi piena, messaggio scartato")
            else:
                self.message_received.emit(msg_text)

        async def keep_alive():
            while True:
                try:
                    try:
                        connected = self.client.is_connected()
                    except Exception:
                        connected = False
                    if not connected:
                        logger.warning("Auto-reconnecting...")
                        await self.client.connect()
                    await self.client.get_me()
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.debug("Keep-alive ping failed: %s", e)
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