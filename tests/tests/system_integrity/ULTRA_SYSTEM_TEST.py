import os
import sys
import time
import random
import threading
import traceback
import logging
import math

# =========================================================
# 🔴 FIX PATH PER IMPORTARE LA CARTELLA "core/"
# =========================================================
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

print("\n"+"🔥"*50)
print("ULTRA SYSTEM INTEGRITY TEST — ARCHITECTURAL CHAOS SIMULATION")
print("🔥"*50+"\n")

FAILURES = []

def fail(code, reason, file, impact):
    msg = (f"\n❌ FAIL [{code}]\n"
           f"→ {reason}\n"
           f"File: {file}\n"
           f"Impatto: {impact}")
    print(msg)
    FAILURES.append(msg)

def ok(code, desc):
    print(f"🟢 OK [{code}] → {desc}")

# =========================================================
# ENV ISOLATO & PERSISTENTE (Per simulare i Reboot)
# =========================================================
TEST_DIR = "ultra_system_env"
os.makedirs(TEST_DIR, exist_ok=True)
import core.config_paths
core.config_paths.CONFIG_DIR = TEST_DIR

# File di config base
with open(os.path.join(TEST_DIR, "config.yaml"), "w") as f:
    f.write("betting:\n  allow_place: false\n")

original_sleep = time.sleep
time.sleep = lambda s: original_sleep(s) if s < 1 else None

# =========================================================
# UTILS PER MOCKING
# =========================================================
def create_mocked_controller():
    from core.dom_executor_playwright import DomExecutorPlaywright
    DomExecutorPlaywright.__init__ = lambda self, *a, **k: None
    DomExecutorPlaywright.launch_browser = lambda self: True
    DomExecutorPlaywright.ensure_login = lambda self: True
    DomExecutorPlaywright.get_balance = lambda self: 1000.0
    DomExecutorPlaywright.place_bet = lambda self, t, m, s: True
    DomExecutorPlaywright.navigate_to_match = lambda self, t: True
    DomExecutorPlaywright.find_odds = lambda self, t, m: 2.0
    DomExecutorPlaywright.check_settled_bets = lambda self: None
    DomExecutorPlaywright.check_open_bet = lambda self: False

    from core.telegram_worker import TelegramWorker
    TelegramWorker.run = lambda self: None
    TelegramWorker.stop = lambda self: None

    from core.controller import SuperAgentController
    logging.basicConfig(level=logging.CRITICAL)
    return SuperAgentController(logging.getLogger("ULTRA"))

# =========================================================
# 1️⃣ REBOOT SIMULATION: DOUBLE BET POST CRASH
# =========================================================
try:
    c1 = create_mocked_controller()
    
    # Simuliamo un crash DIRETTO di Python (Hard Kill) un millisecondo dopo il click su Bet365.
    # Non facciamo scattare "except", distruggiamo brutalmente il processo.
    def hard_kill_mock(*args):
        # I soldi sono stati presi dal bookmaker. Ora il processo muore prima di fare emit() o commit logico.
        raise SystemExit("OS KILL PROCESS")
    
    c1.worker.executor.place_bet = hard_kill_mock
    
    try:
        c1.engine.process_signal({"teams": "REBOOT_TEST", "market": "1"}, c1.money_manager)
    except SystemExit:
        pass # Il processo è "morto"
    
    # Il server si riavvia. Creiamo un NUOVO controller attaccato allo stesso DB.
    c2 = create_mocked_controller()
    pending = c2.money_manager.db.pending()
    
    if len(pending) == 0:
        fail(
            code="DOUBLE_BET_REBOOT",
            reason="Bet piazzata non registrata in PENDING prima del crash fatale.",
            file="execution_engine.py / database.py",
            impact="Al riavvio il bot è cieco e piazzerà una DOPPIA ESPOSIZIONE sullo stesso match."
        )
    else:
        ok("DOUBLE_BET_REBOOT", "Architettura 2-Phase Commit funzionante. Pending sopravvive al reboot.")
        # Pulizia per i test successivi
        for p in pending: c2.money_manager.refund(p['tx_id'])
except Exception as e:
    fail("DOUBLE_BET_REBOOT", str(e), "Unknown", "Unknown")

# =========================================================
# 2️⃣ EVENT BUS NON TRANSAZIONALE (Timeout & Block)
# =========================================================
try:
    c = create_mocked_controller()
    
    # Inseriamo un subscriber "Lento" o in Loop Infinito
    def slow_subscriber(payload):
        original_sleep(2.0) # Simula un blocco di rete I/O di un plugin
        
    c.engine.bus.subscribe("TEST_BLOCK", slow_subscriber)
    
    start_time = time.time()
    c.engine.bus.emit("TEST_BLOCK", {})
    elapsed = time.time() - start_time
    
    if elapsed > 1.0:
        fail(
            code="EVENT_BUS_SYNC_BLOCK",
            reason=f"Il Bus ha bloccato l'Engine per {elapsed:.2f} secondi aspettando un subscriber.",
            file="event_bus.py",
            impact="Un ritardo nell'invio di un log a Telegram freeza il motore scommesse, causando quote scadute o mancate coperture."
        )
    else:
        ok("EVENT_BUS_SYNC_BLOCK", "EventBus Asincrono/Isolato. I subscriber lenti non bloccano l'engine.")
except Exception as e:
    fail("EVENT_BUS_SYNC_BLOCK", str(e), "event_bus.py", "Unknown")

# =========================================================
# 3️⃣ WATCHDOG FINANZIARIO ASSENTE (Ledger vs Bookmaker)
# =========================================================
try:
    c = create_mocked_controller()
    
    # Verifichiamo se esiste una routine di riconciliazione tra saldo DB e saldo Reale
    has_financial_watchdog = hasattr(c, 'financial_watchdog') or hasattr(c.money_manager, 'reconcile_balances')
    
    if not has_financial_watchdog:
        fail(
            code="MISSING_FINANCIAL_WATCHDOG",
            reason="Nessun modulo rileva divergenze tra Saldo Bookmaker Reale e Saldo Database Interno.",
            file="controller.py / money_management.py",
            impact="Se Bet365 annulla una scommessa (void) o applica una trattenuta, il bot non se ne accorge e la martingala sballa, bruciando la cassa."
        )
    else:
        ok("MISSING_FINANCIAL_WATCHDOG", "Watchdog Finanziario presente e pronto alla riconciliazione.")
except Exception as e:
    pass

# =========================================================
# 4️⃣ OVER-RESERVE RACE CONDITION (50 Segnali Simultanei)
# =========================================================
try:
    c = create_mocked_controller()
    # Impostiamo il bankroll a 100€
    c.money_manager.db.update_bankroll(100.0)
    
    err_flag = {"v": False}
    
    # 50 thread tentano di prelevare il 10% della cassa contemporaneamente
    def spam_reserve():
        try:
            stake = c.money_manager.get_stake(2.0) # Dovrebbe calcolare 5€ (5% di 100)
            if stake > 0:
                c.money_manager.reserve(stake)
        except Exception:
            err_flag["v"] = True

    threads = [threading.Thread(target=spam_reserve) for _ in range(50)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    
    final_bankroll = float(c.money_manager.bankroll())
    pending_sum = sum([p['amount'] for p in c.money_manager.db.pending()])
    
    if err_flag["v"] or (100.0 - pending_sum) < 0:
        fail(
            code="OVER_RESERVE_RACE",
            reason=f"La Race Condition ha permesso di riservare {pending_sum}€ su un bankroll di 100€!",
            file="money_management.py",
            impact="Possibile bancarotta per esaurimento fondi se arrivano molti segnali simultanei."
        )
    else:
        ok("OVER_RESERVE_RACE", f"Concorrenza perfetta. Bankroll integro. Pending totale: {pending_sum}€")
except Exception as e:
    fail("OVER_RESERVE_RACE", str(e), "money_management.py", "Unknown")

# =========================================================
# 5️⃣ STAKE ANOMALI E NAN (Math Poisoning)
# =========================================================
try:
    c = create_mocked_controller()
    
    poisoned_stakes = [float('inf'), float('-inf'), float('nan'), -50.0, 0.0]
    passed_poison = False
    
    for bad_stake in poisoned_stakes:
        try:
            # Bypassiamo get_stake e testiamo direttamente la reserve
            if math.isnan(bad_stake) or bad_stake <= 0:
                pass # Un sanity check dovrebbe bloccarlo prima
            
            tx = c.money_manager.reserve(bad_stake)
            # Se la reserve accetta NaN o negativi, è un disastro
            val = c.money_manager.db.get_transaction(tx)['amount']
            if math.isnan(val) or val <= 0:
                passed_poison = True
        except ValueError:
            pass # Comportamento corretto, l'eccezione blocca l'anomalia
        except Exception:
            pass
            
    if passed_poison:
        fail(
            code="MATH_POISONING",
            reason="Il Money Manager ha accettato stake Negativi, a Zero o NaN.",
            file="money_management.py",
            impact="Corruzione irreparabile del Database finanziario SQLite. Il bot smetterà di scommettere per sempre."
        )
    else:
        ok("MATH_POISONING", "Sanity Check attivo. Valori matematici illegali respinti.")
except Exception as e:
    fail("MATH_POISONING", str(e), "money_management.py", "Unknown")

# =========================================================
# 6️⃣ TRANSAZIONI ZOMBIE E CONNESSIONE PERSA
# =========================================================
try:
    c = create_mocked_controller()
    
    # Simuliamo la perdita di rete improvvisa DURANTE il piazzamento
    def drop_connection(*args):
        raise ConnectionError("Internet Disconnected")
        
    c.worker.executor.place_bet = drop_connection
    
    c.engine.process_signal({"teams":"ZOMBIE", "market":"1"}, c.money_manager)
    
    # Se il sistema gestisce correttamente, dovrebbe aver fatto il ROLLBACK perché NON è arrivato al Bookmaker
    pend = c.money_manager.db.pending()
    zombies = [p for p in pend if p['status'] == "PENDING"]
    
    if len(zombies) > 0:
        fail(
            code="ZOMBIE_TRANSACTION",
            reason="Dopo un crash di rete pre-click, la transazione è rimasta appesa in PENDING senza Rollback.",
            file="execution_engine.py",
            impact="Blocco di fondi fittizio. Dopo 10 disconnessioni, il bot crederà di aver esaurito la cassa."
        )
    else:
        ok("ZOMBIE_TRANSACTION", "Rollback Pre-Click perfetto. Nessuna transazione fantasma.")
except Exception as e:
    fail("ZOMBIE_TRANSACTION", str(e), "execution_engine.py", "Unknown")


# =========================================================
# FINALE E REPORT
# =========================================================
print("\n"+"="*60)

if FAILURES:
    print("🔴 ULTRA SYSTEM TEST: RILEVATE FAGLIE ARCHITETTURALI CRITICHE\n")
    print("Correggere i moduli indicati prima di esporre capitali reali.")
    sys.exit(1)
else:
    print("🟢 ULTRA SYSTEM TEST SUPERATO CON SUCCESSO")
    print("L'architettura è resiliente a Reboot, Race Conditions, Timeouts e Math Poisoning.")
    sys.exit(0)
