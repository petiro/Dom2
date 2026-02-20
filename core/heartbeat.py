import os
import time
import threading
from pathlib import Path

HEARTBEAT_FILE = os.path.join(str(Path.home()), ".superagent_data", "heartbeat.dat")

class AppHeartbeat:
    @staticmethod
    def start():
        def _pulse():
            while True:
                try:
                    with open(HEARTBEAT_FILE, "w") as f:
                        f.write(str(time.time()))
                except Exception: pass
                time.sleep(10) # Batti ogni 10 secondi
                
        t = threading.Thread(target=_pulse, daemon=True)
        t.start()
