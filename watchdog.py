"""
SuperAgent Watchdog - External Immortality Layer
Monitors the main process and restarts on crash (exit code != 0).
Place in shell:startup for H24 auto-boot after blackout / Windows Update.
Uses subprocess.Popen + process.wait() — zero CPU spin.
"""
import subprocess
import time
import os
import sys
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MAIN_SCRIPT = os.path.join(BASE_DIR, "main.py")
LOG_FILE = os.path.join(BASE_DIR, "logs", "watchdog.log")

os.makedirs(os.path.join(BASE_DIR, "logs"), exist_ok=True)


def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


log("Watchdog started")

while True:
    log("Starting SuperAgent...")
    process = subprocess.Popen([sys.executable, MAIN_SCRIPT])
    process.wait()  # Blocks efficiently (no CPU spin) until process exits

    if process.returncode == 0:
        log("SuperAgent exited normally (code 0). Stopping watchdog.")
        break

    log(f"Crash detected (exit code: {process.returncode}). Restarting in 5s...")
    time.sleep(5)
