import os
import asyncio
from queue import Full
from PySide6.QtCore import QThread, Signal
from telethon import TelegramClient, events

class TelegramWorker(QThread):
    # Signals definiti correttamente
    message_received = Signal(str)      # Payload: solo il testo
    status_changed = Signal(str)        # Payload: messaggio di stato
    error_occurred = Signal(str)        # Payload: messaggio di errore

    def __init__(self, config, message_queue=None):
        super().__init__()
        self.message_queue = message_queue
        self.client = None
        self.loop = None
        self.keep_alive_task = None
        
        # --- CONFIG VALIDATION SAFE ---
        try:
            self.api_id = int(config.get('api_id', 0))
            if self.api_id == 0: raise ValueError("API ID mancante o 0")
        except (ValueError, TypeError):
            self.api_id = None 
            
        self.api_hash = config.get('api_hash', '')

        # --- CHATS TYPE CHECK ---
        raw_chats = config.get('selected_chats', [])
        if isinstance(raw_chats, str):
            self.selected_chats = [raw_chats]
        elif isinstance(raw_chats, list):
            self.selected_chats = raw_chats
        else:
            self.selected_chats = []

        # Path sicuro per la sessione
        _base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self._data_dir = os.path.join(_base, "data")
        os.makedirs(self._data_dir, exist_ok=True)

    def run(self):
        """Inizializza l'event loop isolato per questo thread"""
        if not self.api_id or not self.api_hash:
            self.error_occurred.emit("CONFIG ERROR: API ID o HASH mancanti/invalidi")
            return

        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        try:
            self.loop.run_until_complete(self._main())
        except Exception as e:
            self.error_occurred.emit(f"CRITICAL LOOP ERROR: {str(e)}")
        finally:
            if not self.loop.is_closed():
                self.loop.close()

    async def _main(self):
        session_path = os.path.join(self._data_dir, "session_v4")
        self.client = TelegramClient(session_path, self.api_id, self.api_hash)
        
        # --- ENTERPRISE FIX: NO START() ---
        self.status_changed.emit("Connessione in corso...")
        try:
            await self.client.connect()
        except Exception as e:
            self.error_occurred.emit(f"CONNECTION FAILED: {str(e)}")
            return
        
        # Controllo Autenticazione senza input()
        if not await self.client.is_user_authorized():
            self.status_changed.emit("Richiesto Login")
            self.error_occurred.emit("SESSION_MISSING: Esegui l'app con --console per il primo login.")
            await self.client.disconnect()
            return

        self.status_changed.emit("Connesso")

        # Handler Messaggi
        @self.client.on(events.NewMessage(chats=self.selected_chats if self.selected_chats else None))
        async def handler(event):
            msg_text = event.raw_text
            if self.message_queue:
                try: 
                    self.message_queue.put_nowait(msg_text)
                except Full: 
                    pass
            else:
                self.message_received.emit(msg_text)

        # Keep-Alive Task
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
        if self.loop and self.loop.is_running():
            async def shutdown():
                if self.keep_alive_task:
                    self.keep_alive_task.cancel()
                if self.client:
                    await self.client.disconnect()
            asyncio.run_coroutine_threadsafe(shutdown(), self.loop)
        self.quit()
        self.wait(2000)
