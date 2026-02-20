import os
import sys
import time
import threading
import traceback
import logging
import psutil
import signal

print("\n" + "="*60)
print("🧠 DOM2 HEDGE FUND STABILITY TEST (V8.4)")
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
# Poiché GitHub non può accedere a Bet365 (IP bloccati) e il match è finto,
# dobbiamo simulare il successo della navigazione SOLO per questo test.
from core.dom_executor_playwright import DomExecutorPlaywright

# A. Patch Init (Headless)
orig_init = DomExecutorPlaywright.__init__
def patched_init(self, *args, **kwargs):
    kwargs["headless"] = True
    print("🔧 HEDGE: Executor forzato in Headless Mode")
    orig_init(self, *args, **kwargs)
DomExecutorPlaywright.__init__ = patched_init

# B. Patch Navigazione (Simuliamo successo)
def mocked_navigate(self, teams):
    print(f"🔧 HEDGE MOCK: Navigazione simulata OK verso {teams}")
    return True
DomExecutorPlaywright.navigate_to_match = mocked_navigate

# C. Patch Quote (Simuliamo quota trovata)
def mocked_odds(self, teams, market):
    print(f"🔧 HEDGE MOCK: Quota simulata trovata (1.50)")
    return 1.50
DomExecutorPlaywright.find_odds = mocked_odds

# D. Patch Scommessa (Simuliamo click scommessa)
def mocked_place(self, teams, market, stake):
    print(f"🔧 HEDGE MOCK: Scommessa piazzata simulata ({stake}€)")
    # Simuliamo il tempo di attesa della ricevuta
    time.sleep(1)
    return True
DomExecutorPlaywright.place_bet = mocked_place

# E. Patch check_open_bet (Evita blocco iniziale e timeout di rete)
def mocked_check_open(self):
    print("🔧 HEDGE MOCK: check_open_bet simulato (Nessuna bet aperta)")
    return False
DomExecutorPlaywright.check_open_bet = mocked_check_open

# F. Patch get_balance (Evita blocco verifica fondi)
def mocked_get_balance(self):
    print("🔧 HEDGE MOCK: get_balance simulato (1000.0€)")
    return 1000.0
DomExecutorPlaywright.get_balance = mocked_get_balance

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

# Timeout di sicurezza brutale (3 minuti)
if hasattr(signal, "SIGALRM"):
    signal.signal(signal.SIGALRM, lambda s, f: sys.exit(1))
    signal.alarm(180)

# ---------------------------------------------------
# 5. AVVIO SISTEMA
# ---------------------------------------------------
try:
    print("🚀 Avvio Controller...")
    controller = SuperAgentController(logger)
    print("✅ Controller avviato.")
except Exception as e:
    print(f"❌ CONTROLLER CRASH ALL'AVVIO: {e}")
    sys.exit(1)

time.sleep(5) # Warmup

# Verifica immediata Worker Thread
if not controller.worker.thread.is_alive():
    print("❌ CRITICAL: Worker Thread morto subito dopo l'avvio!")
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
    "sport": "SOCCER"
}

print("💉 INIEZIONE SEGNALE TEST...")
controller.handle_signal(fake_signal)

# ---------------------------------------------------
# 7. FREEZE DETECTOR LOOP
# ---------------------------------------------------
print("⏳ Monitoraggio Runtime (Max 60s)...")
start_time = time.time()
while time.time() - start_time < 60:
    # A. Controllo se il test è finito
    if result["status"] == "WIN": # Ora ci aspettiamo una WIN perché abbiamo mockato il successo
        break
    
    # B. Controllo se Python è crashato
    if crash_flag["dead"]:
        print("❌ CRASH RILEVATO DAL WATCHDOG")
        sys.exit(1)
    
    # C. Controllo se il worker è morto silenziosamente
    if not controller.worker.thread.is_alive():
        print("❌ WORKER THREAD MORTO DURANTE L'ESECUZIONE")
        sys.exit(1)

    time.sleep(1)

# ---------------------------------------------------
# 8. AUDIT FINALE (Database & Memoria)
# ---------------------------------------------------
print("\n🔍 AUDIT SISTEMA...")

# A. Controllo Database (Scrittura fisica su disco)
try:
    rows = controller.db.conn.execute("SELECT * FROM journal").fetchall()
    print(f"📊 DB Journal Entries: {len(rows)}")
    if len(rows) == 0:
        print("❌ DB FAIL: Nessuna transazione scritta nel database!")
        sys.exit(1)
except Exception as e:
    print(f"❌ DB ACCESS ERROR: {e}")
    sys.exit(1)

# B. Controllo Memory Leak
try:
    process = psutil.Process(os.getpid())
    mem_mb = process.memory_info().rss / 1024 / 1024
    print(f"🧠 RAM Usage: {mem_mb:.2f} MB")

    if mem_mb > 800: # Soglia di allarme
        print("❌ MEMORY LEAK SOSPETTO: Consumo RAM eccessivo!")
        sys.exit(1)
except:
    pass

# ---------------------------------------------------
# 9. SHUTDOWN & VERDETTO
# ---------------------------------------------------
controller.worker.stop()
bus.stop()

if result["status"] == "WAITING":
    print("\n❌ TIMEOUT: Il sistema non ha risposto (Freeze Probabile)")
    sys.exit(1)

print("\n" + "="*60)
print(f"🟢 HEDGE TEST PASSATO: Sistema Stabile. Esito: {result['status']}")
print("="*60)
sys.exit(0)
