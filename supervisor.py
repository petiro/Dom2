import sys
import os
import time
import subprocess
import psutil
from datetime import datetime
from pathlib import Path

BOT_EXECUTABLE = "main.py" 
HEARTBEAT_FILE = os.path.join(str(Path.home()), ".superagent_data", "heartbeat.dat")
MAX_TIMEOUT = 60 # Secondi senza battito prima di killare

def log(msg):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [SUPERVISOR] {msg}")

def kill_process_tree(pid):
    try:
        parent = psutil.Process(pid)
        for child in parent.children(recursive=True):
            child.kill()
        parent.kill()
    except Exception:
        pass

def run_supervisor():
    log("🛡️ Avvio Supervisor: Heartbeat Monitor (OS-Level) Attivo.")
    
    while True:
        log("🚀 Avvio sistema Core...")
        
        # Resetta heartbeat per evitare falsi positivi
        if os.path.exists(HEARTBEAT_FILE): os.remove(HEARTBEAT_FILE)
            
        process = subprocess.Popen([sys.executable, BOT_EXECUTABLE])
        
        while process.poll() is None:
            time.sleep(15)
            # Controllo Anti-Freeze (Deadlock/100% CPU)
            if os.path.exists(HEARTBEAT_FILE):
                try:
                    with open(HEARTBEAT_FILE, "r") as f:
                        last_beat = float(f.read().strip())
                    
                    if time.time() - last_beat > MAX_TIMEOUT:
                        log("☠️ FREEZE RILEVATO: L'Heartbeat è fermo da > 60s. Esecuzione HARD KILL.")
                        kill_process_tree(process.pid)
                        break # Esce dal loop e riavvia
                except Exception: pass

        log(f"⚠️ Il processo principale è terminato/killato. Riavvio in 5 secondi...")
        time.sleep(5)

if __name__ == "__main__":
    run_supervisor()
