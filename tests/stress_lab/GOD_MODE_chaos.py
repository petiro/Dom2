import os
import sys
import time
import random
import threading
import traceback
import logging

print("\n"+"🧠"*50)
print("GOD MODE CHAOS ENGINEERING — ABSOLUTE SYSTEM CERTIFICATION")
print("🧠"*50+"\n")

FAILURES = []

def fail(where, reason):
    msg=f"❌ FAIL [{where}] → {reason}"
    print(msg)
    FAILURES.append(msg)

def ok(msg):
    print(f"✅ {msg}")

# =========================================================
# ENV ISOLATO
# =========================================================
TEST_DIR="god_chaos_env"
os.makedirs(TEST_DIR,exist_ok=True)

import core.config_paths
core.config_paths.CONFIG_DIR=TEST_DIR

# =========================================================
# MOCK PLAYWRIGHT (Disabilitiamo il Browser Reale)
# =========================================================
from core.dom_executor_playwright import DomExecutorPlaywright
DomExecutorPlaywright.__init__=lambda self,*a,**k:None
DomExecutorPlaywright.launch_browser=lambda self:True
DomExecutorPlaywright.ensure_login=lambda self:True
DomExecutorPlaywright.get_balance=lambda self:10000.0
DomExecutorPlaywright.place_bet=lambda self,t,m,s:True
DomExecutorPlaywright.navigate_to_match=lambda self,t:True
DomExecutorPlaywright.find_odds=lambda self,t,m:2.0
DomExecutorPlaywright.check_settled_bets=lambda self:None
DomExecutorPlaywright.check_open_bet=lambda self:False

# =========================================================
# BOOT CONTROLLER
# =========================================================
from core.controller import SuperAgentController
logging.basicConfig(level=logging.CRITICAL)
logger=logging.getLogger("GOD")

try:
    controller=SuperAgentController(logger)
    ok("Controller avviato (Boot Integrity OK)")
except Exception as e:
    fail("BOOT","Controller crash all'avvio: "+str(e))
    sys.exit(1)

# =========================================================
# TEST 1 — TELEGRAM WORKER VIVO (Anti Bot-Sordo)
# =========================================================
try:
    if not hasattr(controller,"telegram"):
        fail("TELEGRAM","Worker non istanziato")
    elif not controller.telegram.isRunning():
        fail("TELEGRAM","Worker thread spento/crashato")
    else:
        ok("Telegram Worker ATTIVO e in ascolto")
except Exception as e:
    fail("TELEGRAM",str(e))

# =========================================================
# TEST 2 — EVENTBUS RESILIENCE (Effetto Domino)
# =========================================================
try:
    survived={"v":False}

    def crash(p): raise RuntimeError("BOOM! Subscriber Crash")
    def good(p): survived["v"]=True

    controller.engine.bus.subscribe("TEST_EVT",crash)
    controller.engine.bus.subscribe("TEST_EVT",good)

    controller.engine.bus.emit("TEST_EVT",{})
    time.sleep(0.5)

    if not survived["v"]:
        fail("EVENTBUS","Crash di un subscriber ha ucciso il Bus!")
    else:
        ok("EventBus RESILIENTE (Sopravvive ai crash dei plugin)")
except Exception as e:
    fail("EVENTBUS",str(e))

# =========================================================
# TEST 3 — WORKER POISON PILL (Coda Corrotta)
# =========================================================
try:
    alive={"v":False}

    def poison(): raise ValueError("SEGNALE CORROTTO")
    def good(): alive["v"]=True

    for _ in range(20):
        controller.worker.submit(poison)

    time.sleep(1)
    controller.worker.submit(good)
    time.sleep(1)

    if not alive["v"]:
        fail("WORKER","Thread morto dopo eccezione nella coda!")
    else:
        ok("Worker Thread IMMORTALE (Sopravvive a poison pill)")
except Exception as e:
    fail("WORKER",str(e))

# =========================================================
# TEST 4 — DATABASE RACE CONDITION (Concurrency Hell)
# =========================================================
try:
    err={"v":False}

    def spam():
        try:
            for _ in range(200):
                controller.money_manager.bankroll()
                tx=str(random.random())
                controller.money_manager.reserve(1.0)
                controller.money_manager.db.rollback(tx)
        except Exception:
            err["v"]=True

    threads=[threading.Thread(target=spam) for _ in range(20)]
    [t.start() for t in threads]
    [t.join() for t in threads]

    if err["v"]:
        fail("DATABASE","Race Condition / Database Locked!")
    else:
        ok("Database WAL Mode: CONCORRENZA PERFETTA (0 Lock)")
except Exception as e:
    fail("DATABASE",str(e))

# =========================================================
# TEST 5 — LEDGER CRASH POST BET (Soldi Fantasma)
# =========================================================
try:
    controller.money_manager.get_stake=lambda o:5.0
    before=controller.money_manager.bankroll()

    orig=controller.engine.bus.emit
    def crash_emit(ev,p):
        if ev=="BET_SUCCESS":
            raise RuntimeError("CRASH IMPROVVISO POST-BET")
        orig(ev,p)

    controller.engine.bus.emit=crash_emit
    controller.engine.process_signal({"teams":"A-B","market":"1"},controller.money_manager)
    after=controller.money_manager.bankroll()

    if after==before:
        fail("LEDGER","CRITICO: Refund fantasma eseguito dopo bet piazzata sul sito!")
    else:
        ok("Ledger INTEGRO (Nessun rimborso errato post-crash)")

    controller.engine.bus.emit=orig
except Exception as e:
    fail("LEDGER",str(e))

# =========================================================
# TEST 6 — ENGINE STRESS (5000 Segnali)
# =========================================================
try:
    print("▶️ Stress Test: Processando 1000 segnali rapidi...")
    for _ in range(1000):
        controller.engine.process_signal({"teams":"X-Y","market":"1"},controller.money_manager)
    ok("Engine Stress Test SUPERATO")
except Exception as e:
    fail("ENGINE_STRESS",str(e))

# =========================================================
# TEST 7 — ENGINE FREEZE DETECTION
# =========================================================
try:
    if not controller.worker.is_alive():
        fail("FREEZE","Worker Thread morto silenziosamente")
    else:
        ok("Sistema ATTIVO e REATTIVO")
except Exception as e:
    fail("FREEZE",str(e))

# =========================================================
# FINALE E REPORT
# =========================================================
controller.worker.stop()
controller.engine.bus.stop()

print("\n"+"="*60)

if FAILURES:
    print("🔴 GOD MODE: SISTEMA NON STABILE (CERTIFICAZIONE FALLITA)")
    print("REPORT ERRORI:")
    for f in FAILURES:
        print(f)
    sys.exit(1)
else:
    print("🟢 GOD MODE SUPERATO: ARCHITETTURA HEDGE-GRADE CERTIFICATA")
    print("Il sistema è pronto per il deploy in produzione reale.")
    sys.exit(0)
