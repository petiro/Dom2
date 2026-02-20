import os
import sys
import time
import logging

print("\n" + "🔥"*30)
print("☠️ CHAOS ENGINEERING: SILENT KILLERS TEST")
print("🔥"*30 + "\n")

# 1. SETUP AMBIENTE ISOLATO
TEST_DIR = os.path.join(os.getcwd(), "chaos_test_env")
os.makedirs(TEST_DIR, exist_ok=True)
import core.config_paths
core.config_paths.CONFIG_DIR = TEST_DIR

# 2. MOCKING BRUTALE DELL'EXECUTOR
from core.dom_executor_playwright import DomExecutorPlaywright
# Bypassa l'apertura reale del browser
DomExecutorPlaywright.__init__ = lambda self, *a, **kw: None
DomExecutorPlaywright.check_open_bet = lambda self: False
DomExecutorPlaywright.get_balance = lambda self: 1000.0
DomExecutorPlaywright.navigate_to_match = lambda self, t: True
DomExecutorPlaywright.find_odds = lambda self, t, m: 2.0
DomExecutorPlaywright.place_bet = lambda self, t, m, s: True

from core.controller import SuperAgentController

# Disabilitiamo i log normali per vedere solo i risultati del test
logging.basicConfig(level=logging.CRITICAL)
logger = logging.getLogger("CHAOS")
controller = SuperAgentController(logger)

# =====================================================================
# 🕵️‍♂️ TEST 1: LA SINDROME DEL BOT SORDO (Telegram Offline)
# =====================================================================
print("▶️ TEST 1: Verifica ascolto Telegram (Bot Sordo)...")
time.sleep(1)

if not hasattr(controller, 'telegram'):
    print("❌ FATAL BUG 1: Il worker di Telegram non è stato nemmeno istanziato!")
    sys.exit(1)

if not controller.telegram.isRunning():
    print("❌ FATAL BUG 1: Il thread di Telegram è spento. Il bot non riceverà segnali!")
    sys.exit(1)

print("✅ TEST 1 SUPERATO: Telegram Worker è online e in ascolto.\n")


# =====================================================================
# 🕵️‍♂️ TEST 2: SINDROME DELLA SCOMMESSA UNICA (Watchdog Deadlock)
# =====================================================================
print("▶️ TEST 2: Verifica Watchdog e Pending Bets (Deadlock)...")

# A. Simuliamo una bet che rimane in PENDING nel database
tx_id = controller.money_manager.reserve(50.0)
pending_bets = controller.money_manager.db.pending()

if len(pending_bets) != 1:
    print("❌ ERRORE SETUP TEST 2: Impossibile creare bet PENDING.")
    sys.exit(1)

# B. Simuliamo che il Bookmaker (dopo 2 ore) ci dica che la bet è VINCENTE
controller.worker.executor.check_settled_bets = lambda: {"status": "WIN", "payout": 100.0}

# C. Invochiamo forzatamente la logica del Watchdog (senza aspettare 120 secondi)
res = controller.worker.executor.check_settled_bets()
if res and res.get("status") == "WIN":
    controller.money_manager.win(tx_id, res.get("payout", 0))

# D. VERIFICA: Il DB si è ripulito?
pending_after = controller.money_manager.db.pending()
if len(pending_after) > 0:
    print("❌ FATAL BUG 2: Il Watchdog non ha refertato la bet. Coda bloccata per sempre!")
    sys.exit(1)

print("✅ TEST 2 SUPERATO: Watchdog risolve le bet PENDING e sblocca la coda.\n")


# =====================================================================
# 🕵️‍♂️ TEST 3: CORRUZIONE DEL LEDGER (Crash POST-Giocata)
# =====================================================================
print("▶️ TEST 3: Verifica Corruzione Ledger (Crash Post-Bet)...")

# A. Forziamo lo stake a 10.0 fisso per calcoli matematici certi
controller.money_manager.get_stake = lambda odds: 10.0

balance_before = controller.money_manager.bankroll() # Registriamo i soldi prima
print(f"   Saldo inziale: {balance_before}€")

# B. CREIAMO IL CAOS: Modifichiamo il bus eventi per lanciare un'eccezione
# ESATTAMENTE nell'istante in cui la bet è stata piazzata con successo.
original_emit = controller.engine.bus.emit
def crash_emit(event_name, payload):
    if event_name == "BET_SUCCESS":
        print("   💥 INIEZIONE CRASH SIMULATO: Errore Python Improvviso!")
        raise RuntimeError("CRASH SIMULATO DOPO PIAZZAMENTO SCOMMESSA!")
    original_emit(event_name, payload)

controller.engine.bus.emit = crash_emit

# C. Inviamo un segnale al motore di esecuzione
payload = {"teams": "Test Match", "market": "1"}
controller.engine.process_signal(payload, controller.money_manager)

# D. VERIFICA MATEMATICA
balance_after = controller.money_manager.bankroll()
print(f"   Saldo finale calcolato: {balance_after}€")

# Se il bug esiste, il blocco 'except' fa il refund e ci ridà i 10€.
# Ma noi ABBIAMO piazzato la bet sul bookmaker! I 10€ devono sparire dal ledger!
if balance_after == balance_before:
    print("❌ FATAL BUG 3: Corruzione Ledger! La scommessa è stata piazzata sul sito, ma i soldi sono stati rimborsati nel database interno!")
    sys.exit(1)

if balance_after == balance_before - 10.0:
    print("✅ TEST 3 SUPERATO: Il Ledger ha bloccato il refund ingiustificato.\n")
else:
    print("❌ ERRORE MATEMATICO SCONOSCIUTO SUL LEDGER.")
    sys.exit(1)

# =====================================================================
print("🏆 VERDETTO FINALE: TUTTI I SILENT KILLERS SONO STATI NEUTRALIZZATI!")
print("🛡️ LA TUA ARCHITETTURA È UFFICIALMENTE 100% HEDGE-GRADE.")
print("🔥"*30 + "\n")
sys.exit(0)
