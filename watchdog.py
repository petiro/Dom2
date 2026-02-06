"""
SuperAgent Watchdog - Auto Restart on Crash
"""
import time
import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MAIN_SCRIPT = os.path.join(BASE_DIR, "main.py")

while True:
    print("Avvio agente...")
    exit_code = os.system(f"{sys.executable} {MAIN_SCRIPT}")
    if exit_code == 0:
        print("Agente terminato normalmente.")
        break
    print(f"Crash rilevato (exit code: {exit_code}), riavvio tra 5 sec...")
    time.sleep(5)
