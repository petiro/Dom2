import os
import sys
import time
import logging
import shutil
import threading
import signal # FIX 1: Timeout globale
import psutil # FIX 3: Memory Check

# 1. FORZIAMO CONFIGURAZIONE DI TEST (Isolamento Totale)
TEST_DIR = os.path.join(os.getcwd(), "test_env_ci")
os.makedirs(TEST_DIR, exist_ok=True)

# Patch dei percorsi PRIMA di importare il core
import core.config_paths
core.config_paths.CONFIG_DIR = TEST_DIR

# 2. PATCH PER GITHUB ACTIONS (Headless Mode Obbligatoria)
from core.dom_executor_playwright import DomExecutorPlaywright
original_init = DomExecutorPlaywright.__init__

def patched_init(self, *args, **kwargs):
    kwargs['headless'] = True
    print("🔧 TEST PATCH: Executor forzato in Headless Mode")
    original_init(self, *args, **kwargs)

DomExecutorPlaywright.__init__ = patched_init

# Ora importiamo il Core
from core.controller import SuperAgentController
from core.event_bus import bus
from core.events import AppEvent

# Logger Console
logging.basicConfig(level=logging.INFO, format="%(asctime)s | TESTER | %(message)s")
logger = logging.getLogger("ProductionVerifier")

# --- FIX 1: TIMEOUT HANDLER (SAFETY NET) ---
def timeout_handler(signum, frame):
    print("\n❌ GLOBAL TIMEOUT: Il bot si è congelato (Deadlock o Loop).")
    sys.exit(1)

def run_simulation():
    print("\n" + "="*60)
    print("🚀 GITHUB PRODUCTION SIMULATION V8.4 (MILITARY GRADE)")
    print("="*60)

    # Attiva timeout solo su Linux/Mac (GitHub Actions usa Ubuntu)
    if hasattr(signal, "SIGALRM"):
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(180) # 3 minuti max vita totale
        print("⏰ Timeout di sicurezza attivo (180s).")

    # A. AVVIO CONTROLLER
    try:
        controller = SuperAgentController(logger)
        print("✅ Controller avviato (Database + Worker + Bus attivi).")
    except Exception as e:
        print(f"❌ CRITICAL: Il Controller non parte! {e}")
        sys.exit(1)

    # --- FIX 2: VERIFICA WORKER THREAD VIVO ---
    # Intercetta crash silenziosi prima ancora di mandare segnali
    if not controller.worker.thread or not controller.worker.thread.is_alive():
        print("❌ CRITICAL: Il Worker Thread è morto all'avvio!")
        sys.exit(1)
    else:
        print("✅ Worker Thread: VIVO e OPERATIVO.")

    # B. MONITOR RISULTATI
    results = {"status": "WAITING", "detail": ""}
    
    def on_success(data):
        results["status"] = "SUCCESS"
        results["detail"] = f"Win registrata: {data}"
        print("🏆 EVENTO RICEVUTO: BET_SUCCESS")

    def on_fail(data):
        results["status"] = "HANDLED_ERROR"
        results["detail"] = data.get('reason', 'Unknown')
        print(f"🛡️ EVENTO RICEVUTO: BET_FAILED (Errore gestito: {data.get('reason')})")

    bus.subscribe(AppEvent.BET_SUCCESS, on_success)
    bus.subscribe(AppEvent.BET_FAILED, on_fail)

    # C. ATTESA WARM-UP WORKER
    print("⏳ Attesa warm-up worker (5s)...")
    time.sleep(5)
    
    if not controller.worker.running:
        print("❌ ERRORE: Il Worker Playwright è morto!")
        sys.exit(1)

    # D. INIEZIONE SEGNALE SIMULATO
    print("\n💉 INIEZIONE SEGNALE TEST: 'Final Champions League'...")
    fake_signal = {
        "teams": "Manchester City vs Inter",
        "market": "WINNER",
        "sport": "SOCCER"
    }
    controller.handle_signal(fake_signal)

    # E. ATTESA RISPOSTA (Max 45s)
    print("⏳ Attesa elaborazione bot...")
    for _ in range(45):
        if results["status"] != "WAITING":
            break
        time.sleep(1)
        print(".", end="", flush=True)
    print("\n")

    # F. VERIFICA DATABASE (ACID CHECK)
    print("🔍 VERIFICA DATABASE...")
    try:
        logs = controller.db.conn.execute("SELECT * FROM journal").fetchall()
        print(f"✅ DB Check: {len(logs)} transazioni nel journal.")
    except Exception as e:
        print(f"❌ DB Check Fallito: {e}")
        sys.exit(1)

    # G. REPORT FINALE
    controller.worker.stop()
    bus.stop()

    # --- FIX 3: PRINT RAM USAGE (DEBUG PRO) ---
    try:
        process = psutil.Process(os.getpid())
        mem_mb = process.memory_info().rss / 1024 ** 2
        print(f"📊 MEMORY USAGE: {mem_mb:.2f} MB")
    except: pass

    print("\n" + "="*60)
    if results["status"] == "WAITING":
        print("❌ TIMEOUT LOGICO: Il bot non ha risposto in 45 secondi (Freeze?)")
        sys.exit(1)
    else:
        print(f"✅ TEST PASSATO: Il sistema ha risposto con '{results['status']}'")
        print(f"ℹ️ Dettaglio: {results['detail']}")
        print("="*60)
        sys.exit(0)

if __name__ == "__main__":
    run_simulation()
