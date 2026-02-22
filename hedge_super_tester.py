import os
import sys
import time
import threading
import traceback
import logging
import psutil
import signal

print("\n" + "="*60)
print("🧠 DOM2 HEDGE FUND STABILITY TEST (V8.5)")
print("="*60)

# ---------------------------------------------------
# 1. AMBIENTE ISOLATO (Sandbox)
# ---------------------------------------------------
TEST_DIR = os.path.join(os.getcwd(), "ci_test_env")
os.makedirs(TEST_DIR, exist_ok=True)

# Patchiamo i percorsi PRIMA di importare il core
import core.config_paths
core.config_paths.CONFIG_DIR = TEST_DIR

# ---------------------------------------------------
# 2. MOCKING PER GITHUB ACTIONS (FONDAMENTALE)
# ---------------------------------------------------
from core.dom_executor_playwright import DomExecutorPlaywright

# 🔴 FIX NUCLEARE: Disinneschiamo l'apertura FISICA del browser!
def mocked_launch_browser(self):
    print("🔧 HEDGE MOCK: Browser simulato (Nessun Chromium fisico avviato!)")
    return True
DomExecutorPlaywright.launch_browser = mocked_launch_browser

def mocked_ensure_login(self):
    print("🔧 HEDGE MOCK: ensure_login simulato")
    return True
DomExecutorPlaywright.ensure_login = mocked_ensure_login

def mocked_navigate(self, teams):
    print(f"🔧 HEDGE MOCK: Navigazione simulata verso {teams}")
    return True
DomExecutorPlaywright.navigate_to_match = mocked_navigate

def mocked_odds(self, teams, market):
    print("🔧 HEDGE MOCK: Quota simulata trovata (1.50)")
    return 1.50
DomExecutorPlaywright.find_odds = mocked_odds

def mocked_place(self, teams, market, stake):
    print(f"🔧 HEDGE MOCK: Scommessa piazzata simulata ({stake}€)")
    time.sleep(1) # Simula attesa bookmaker
    return True
DomExecutorPlaywright.place_bet = mocked_place

def mocked_check_open(self):
    return False
DomExecutorPlaywright.check_open_bet = mocked_check_open

def mocked_get_balance(self):
    return 1000.0
DomExecutorPlaywright.get_balance = mocked_get_balance

def mocked_check_settled(self):
    return None
DomExecutorPlaywright.check_settled_bets = mocked_check_settled

# ---------------------------------------------------
# 3. IMPORT CORE
# ---------------------------------------------------
try:
    from core.controller import SuperAgentController
    from core.event_bus import bus
    from core.events import AppEvent
except ImportError as e:
    print(f"❌ CRITICAL IMPORT ERROR: {e}")
    sys.exit(1)

logging.basicConfig(level=logging.INFO, format="%(asctime)s | HEDGE | %(message)s")
logger = logging.getLogger("HEDGE")

# ---------------------------------------------------
# 4. GLOBAL CRASH WATCHDOG
# ---------------------------------------------------
crash_flag = {"dead": False}

def global_excepthook(exctype, value, tb):
    print("\n🔥 GLOBAL PYTHON CRASH RILEVATO")
    traceback.print_exception(exctype, value, tb)
    crash_flag["dead"] = True

sys.excepthook = global_excepthook

if hasattr(signal, "SIGALRM"):
    signal.signal(signal.SIGALRM, lambda s, f: sys.exit(1))
    signal.alarm(180)

# ---------------------------------------------------
# 5. AVVIO SISTEMA
# ---------------------------------------------------
try:
    print("🚀 Avvio Controller...")
    controller = SuperAgentController(logger)
    
    # 🔥 FIX 1: Dobbiamo "Accendere" il motore, altrimenti il worker resta None
    print("🔘 Pressione fittizia del bottone START/STOP...")
    controller.start_listening()
    
    # 🔥 FIX 2: Iniettiamo un robot finto attivo per superare i blocchi di sicurezza
    controller._load_robots = lambda: [{"name": "HedgeTestBot", "trigger_words": [], "is_active": True}]
    
    print("✅ Controller avviato.")
except Exception as e:
    print(f"❌ CONTROLLER CRASH ALL'AVVIO: {e}")
    sys.exit(1)

time.sleep(2) # Warmup

if not controller.worker.thread or not controller.worker.thread.is_alive():
    print("❌ CRITICAL: Worker Thread morto (o mai partito) subito dopo l'avvio!")
    sys.exit(1)
print("✅ Worker Thread: VIVO")

# ---------------------------------------------------
# 6. SIMULAZIONE EVENTO
# ---------------------------------------------------
result = {"status": "WAITING"}

def on_success(payload):
    result["status"] = "WIN"
    print(f"🏆 EVENT SUCCESS: {payload}")

def on_fail(payload):
    result["status"] = "FAIL_HANDLED"
    print(f"🛡️ FAIL GESTITO (Expected): {payload.get('reason')}")

bus.subscribe(AppEvent.BET_SUCCESS, on_success)
bus.subscribe(AppEvent.BET_FAILED, on_fail)

fake_signal = {
    "teams": "HEDGE FUND TEST MATCH",
    "market": "WINNER",
    "sport": "SOCCER",
    "raw_text": "hedge fund test match" # Utile per superare il check del parser
}

print("💉 INIEZIONE SEGNALE TEST...")
controller.handle_signal(fake_signal)

# ---------------------------------------------------
# 7. FREEZE DETECTOR LOOP
# ---------------------------------------------------
print("⏳ Monitoraggio Runtime (Max 60s)...")
start_time = time.time()
while time.time() - start_time < 60:
    if result["status"] == "WIN":
        break
    if crash_flag["dead"]:
        print("❌ CRASH RILEVATO DAL WATCHDOG")
        sys.exit(1)
    if not controller.worker.thread or not controller.worker.thread.is_alive():
        print("❌ WORKER THREAD MORTO DURANTE L'ESECUZIONE")
        sys.exit(1)
    time.sleep(1)

# ---------------------------------------------------
# 8. AUDIT FINALE (Database & Memoria)
# ---------------------------------------------------
print("\n🔍 AUDIT SISTEMA...")

try:
    rows = controller.db.conn.execute("SELECT * FROM journal").fetchall()
    print(f"📊 DB Journal Entries: {len(rows)}")
    if len(rows) == 0:
        print("❌ DB FAIL: Nessuna transazione scritta nel database!")
        sys.exit(1)
except Exception as e:
    print(f"❌ DB ACCESS ERROR: {e}")
    sys.exit(1)

try:
    process = psutil.Process(os.getpid())
    mem_mb = process.memory_info().rss / 1024 / 1024
    print(f"🧠 RAM Usage: {mem_mb:.2f} MB")
except:
    pass

# ---------------------------------------------------
# 9. SHUTDOWN & VERDETTO
# ---------------------------------------------------
controller.stop_listening() # 🔥 FIX: Spegnimento pulito
controller.worker.stop()
bus.stop()

if result["status"] == "WAITING":
    print("\n❌ TIMEOUT: Il sistema non ha risposto (Freeze Probabile)")
    sys.exit(1)

print("\n" + "="*60)
print(f"🟢 HEDGE TEST PASSATO: Sistema Stabile. Esito: {result['status']}")
print("="*60)
sys.exit(0)