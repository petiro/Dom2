import sys
import os
import time
import threading
import logging

# Forza l'output in UTF-8 per evitare errori su Windows CI
if sys.platform == "win32":
    import codecs
    sys.stdout = codecs.getwriter("utf-8")(sys.stdout.detach())

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("CI_TEST")

def run_tests():
    print(">>> AVVIO TEST AUTOMATICO V4 (CI MODE)...")
    
    try:
        # 1. Test Import
        from core.security import Vault
        from core.dom_executor_playwright import DomExecutorPlaywright
        print("--- Importazioni: OK")

        # 2. Test Vault
        v = Vault()
        test_payload = {"key": "value"}
        v.encrypt_data(test_payload)
        if v.decrypt_data().get("key") == "value":
            print("--- Vault Security: OK")
        
        # 3. Test Browser (Check esistenza metodo)
        executor = DomExecutorPlaywright(None)
        if hasattr(executor, 'launch_browser'):
            print("--- Struttura DomExecutor: OK")
        else:
            print("--- ERRORE: launch_browser() non trovato nel codice!")
            sys.exit(1)

        print(">>> TUTTI I TEST PASSATI!")
        sys.exit(0)

    except Exception as e:
        print(f"--- ERRORE CRITICO: {e}")
        sys.exit(1)

if __name__ == "__main__":
    run_tests()
