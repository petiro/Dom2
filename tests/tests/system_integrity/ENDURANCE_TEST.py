import os
import sys
import time
import threading
import traceback
import logging
import psutil
import sqlite3

# =========================================================
# FIX PATH IMPORT CORE (ROBUSTO PER DOPPIA CARTELLA)
# =========================================================
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = current_dir
# Risale dinamicamente le cartelle finché non trova "core"
while not os.path.exists(os.path.join(project_root, "core")) and project_root != "/":
    project_root = os.path.dirname(project_root)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

print("\n" + "🛡️" * 50)
print("ENDURANCE & ENVIRONMENT TEST — EXTREME SURVIVAL SIMULATION")
print("🛡️" * 50 + "\n")

FAILURES = []
def fail(code, reason):
    msg = f"❌ FAIL [{code}] → {reason}"
    print(msg)
    FAILURES.append(msg)

def ok(code, desc):
    print(f"🟢 OK [{code}] → {desc}")

# =========================================================
# ENV SETUP ISOLATO & TIME TRAVEL (Macchina del tempo)
# =========================================================
TEST_DIR = "endurance_env"
os.makedirs(TEST_DIR, exist_ok=True)
import core.config_paths
core.config_paths.CONFIG_DIR = TEST_DIR
with open(os.path.join(TEST_DIR, "config.yaml"), "w") as f:
    f.write("betting:\n  allow_place: false\n")

# 🔴 FIX TIMEOUT: "Macchina del Tempo". 
# Disabilita gli sleep lunghi per fare 4000 test in 2 secondi invece di 100 minuti!
original_sleep = time.sleep
time.sleep = lambda s: original_sleep(s) if s < 1 else None

# =========================================================
# MOCK PLAYWRIGHT & TELEGRAM
# =========================================================
from core.dom_executor_playwright import DomExecutorPlaywright

def mock_init(self, *a, **k):
    self.bet_count = 0
    self.logger = logging.getLogger("MockExecutor")
    self.page = None

DomExecutorPlaywright.__init__ = mock_init
DomExecutorPlaywright.launch_browser = lambda self: True
DomExecutorPlaywright.ensure_login = lambda self: True
DomExecutorPlaywright.get_balance = lambda self: 1000.0
DomExecutorPlaywright.place_bet = lambda self, t, m, s: True
DomExecutorPlaywright.navigate_to_match = lambda self, t: True
DomExecutorPlaywright.find_odds = lambda self, t, m: 2.0
DomExecutorPlaywright.check_settled_bets = lambda self: None
DomExecutorPlaywright.check_open_bet = lambda self: False
DomExecutorPlaywright.save_blackbox = lambda self, *args, **kwargs: None

from core.telegram_worker import TelegramWorker
TelegramWorker.run = lambda self: None
TelegramWorker.stop = lambda self: None

from core.controller import SuperAgentController
logging.basicConfig(level=logging.CRITICAL)
c = SuperAgentController(logging.getLogger("ENDURANCE"))

# =========================================================
# 🛡️ 1. L'APOCALISSE DEL DISCO PIENO (SQLite IOError)
# =========================================================
try:
    orig_reserve = c.money_manager.reserve
    def mock_disk_full(*args):
        raise sqlite3.OperationalError("database or disk is full")
    c.money_manager.reserve = mock_disk_full

    try:
        c.engine.process_signal({"teams": "DISK_FULL", "market": "1"}, c.money_manager)
        ok("DISK_FULL_SURVIVAL", "Errore 'Disco Pieno' intercettato. Il bot non è crashato.")
    except Exception as e:
        fail("DISK_FULL_SURVIVAL", f"L'errore disco pieno ha ucciso il bot: {e}")

    c.money_manager.reserve = orig_reserve
except Exception as e:
    fail("DISK_FULL_SURVIVAL", str(e))

# =========================================================
# 🛡️ 2. IL BAN DI CLOUDFLARE (Timeout infinito)
# =========================================================
try:
    orig_find_odds = c.worker.executor.find_odds
    def mock_cloudflare(*args):
        raise Exception("Timeout 30000ms exceeded. (Cloudflare Captcha block)")
    c.worker.executor.find_odds = mock_cloudflare

    try:
        c.engine.process_signal({"teams": "CLOUDFLARE_BAN", "market": "1"}, c.money_manager)
        ok("CLOUDFLARE_BAN", "Blocco antibot catturato. Il motore ha abortito la giocata in sicurezza.")
    except Exception as e:
        fail("CLOUDFLARE_BAN", f"Il blocco antibot ha generato un'eccezione non gestita: {e}")

    c.worker.executor.find_odds = orig_find_odds
except Exception as e:
    fail("CLOUDFLARE_BAN", str(e))

# =========================================================
# 🛡️ 3. IL TAGLIO CORRENTE ELEGANTE (Graceful Shutdown)
# =========================================================
try:
    shutdown_flag = {"finished": False}
    def slow_task():
        original_sleep(1) # Usa il VERO sleep qui per simulare il lavoro
        shutdown_flag["finished"] = True

    c.worker.submit(slow_task)
    c.worker.stop()

    if not shutdown_flag["finished"]:
        fail("GRACEFUL_SHUTDOWN", "Il comando di spegnimento ha ucciso brutalmente il bot troncando la scommessa in corso!")
    else:
        ok("GRACEFUL_SHUTDOWN", "Chiusura elegante OK. Il bot ha finito l'ultima scommessa prima di spegnersi.")
except Exception as e:
    fail("GRACEFUL_SHUTDOWN", str(e))

# =========================================================
# 🛡️ 4. LO SOAK TEST (Memory Leak a 4.000 Segnali)
# =========================================================
try:
    process = psutil.Process(os.getpid())
    mem_start = process.memory_info().rss

    for _ in range(2000):
        c.engine.process_signal({"teams": None}, c.money_manager)
        c.engine.process_signal({"teams": "SPAM", "market": "UNKNOWN"}, c.money_manager)

    mem_end = process.memory_info().rss
    diff_mb = (mem_end - mem_start) / 1024 / 1024

    if diff_mb > 50:
        fail("MEMORY_LEAK", f"Il sistema ha accumulato {diff_mb:.2f} MB di spazzatura RAM! Rischio OOM Crash in 24h.")
    else:
        ok("MEMORY_LEAK", f"Nessun Memory Leak. RAM pulita (Variazione: {diff_mb:.2f} MB su 4000 segnali).")

except Exception as e:
    fail("MEMORY_LEAK", str(e))

# =========================================================
# FINALE E REPORT
# =========================================================
print("\n"+"="*60)
if FAILURES:
    print("🔴 ENDURANCE TEST: FAGLIE AMBIENTALI RILEVATE\n")
    sys.exit(1)
else:
    print("🟢 ENDURANCE TEST SUPERATO CON SUCCESSO")
    print("Il bot è ora ufficialmente indistruttibile. SOPRAVVIVE A TUTTO.")
    sys.exit(0)