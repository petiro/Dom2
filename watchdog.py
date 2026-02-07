"""
SuperAgent Watchdog - Auto Restart on Crash
Uses subprocess.Popen + process.wait() to block properly without CPU spin.
"""
import subprocess
import time
import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MAIN_SCRIPT = os.path.join(BASE_DIR, "main.py")

while True:
    print("Avvio agente...")
    process = subprocess.Popen([sys.executable, MAIN_SCRIPT])
    process.wait()  # Blocks efficiently (no CPU spin) until process exits

    if process.returncode == 0:
        print("Agente terminato normalmente.")
        break

    print(f"Crash rilevato (exit code: {process.returncode}), riavvio tra 5 sec...")
    time.sleep(5)
