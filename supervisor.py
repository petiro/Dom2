import sys
import os
import time
import subprocess
import psutil
from datetime import datetime
from pathlib import Path

BOT_EXECUTABLE = "main.py" 
HEARTBEAT_FILE = os.path.join(str(Path.home()), ".superagent_data", "heartbeat.dat")
MAX_TIMEOUT = 60 

def log(msg):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [SUPERVISOR] {msg}")

def kill_process_tree(pid):
    try:
        parent = psutil.Process(pid)
        children = parent.children(recursive=True)
        for child in children:
            try:
                child.kill() # 🔴 FIX: Salta silenziosamente i processi zombie già chiusi
            except psutil.NoSuchProcess:
                pass
        parent.kill()
    except psutil.NoSuchProcess:
        pass
    except Exception as e:
        log(f"Errore durante il kill: {e}")

def run_supervisor():
    log("🛡️ Avvio Supervisor: Heartbeat Monitor (OS-Level) Attivo.")
    
    crash_count = 0  # 🔴 FIX: Anti Loop Infinito
    
    while True:
        log("🚀 Avvio sistema Core...")
        
        if os.path.exists(HEARTBEAT_FILE): 
            os.remove(HEARTBEAT_FILE)
            
        process = subprocess.Popen([sys.executable, BOT_EXECUTABLE])
        
        while process.poll() is None:
            time.sleep(15)
            if os.path.exists(HEARTBEAT_FILE):
                try:
                    with open(HEARTBEAT_FILE, "r") as f:
                        last_beat = float(f.read().strip())
                    
                    if time.time() - last_beat > MAX_TIMEOUT:
                        log("☠️ FREEZE RILEVATO: L'Heartbeat è fermo da > 60s. Esecuzione HARD KILL.")
                        kill_process_tree(process.pid)
                        break 
                except Exception: pass

        # 🔴 Contatore Crash Immediati
        if process.returncode != 0 and process.returncode is not None:
            crash_count += 1
        else:
            crash_count = 0

        if crash_count > 10:
            log("🚨 Troppi crash consecutivi (Loop CPU rilevato). Stop sicurezza per 5 minuti.")
            time.sleep(300)
            crash_count = 0

        log(f"⚠️ Il processo principale è terminato. Riavvio in 5 secondi...")
        time.sleep(5)

if __name__ == "__main__":
    run_supervisor()