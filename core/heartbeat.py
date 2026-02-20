import os
import time
import multiprocessing
from pathlib import Path

DATA_DIR = os.path.join(str(Path.home()), ".superagent_data")
HEARTBEAT_FILE = os.path.join(DATA_DIR, "heartbeat.dat")

class AppHeartbeat:
    @staticmethod
    def _pulse():
        while True:
            try:
                # 🔴 FIX HEDGE-GRADE: Scrittura atomica per l'heartbeat
                tmp_file = HEARTBEAT_FILE + ".tmp"
                with open(tmp_file, "w") as f:
                    f.write(str(time.time()))
                os.replace(tmp_file, HEARTBEAT_FILE)
            except Exception: 
                pass
            time.sleep(10)

    @staticmethod
    def start():
        # 🔴 FIX HEDGE-GRADE: Crea la cartella PRIMA di pulsare
        os.makedirs(DATA_DIR, exist_ok=True)
        # Processo su core CPU isolato
        p = multiprocessing.Process(target=AppHeartbeat._pulse, daemon=True)
        p.start()