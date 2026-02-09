import sys
import os
import logging

# Forza l'output in UTF-8 per evitare UnicodeEncodeError su Windows CI
if sys.platform == "win32":
    import codecs
    if sys.stdout.encoding != 'utf-8':
        sys.stdout = codecs.getwriter("utf-8")(sys.stdout.detach())

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("CI_TEST")

def run_tests():
    print(">>> START: AUTOMATIC TEST V4 (CI MODE)")
    
    try:
        # 1. Test Import (Verifica se le librerie sono installate correttamente)
        from core.security import Vault
        from core.dom_executor_playwright import DomExecutorPlaywright
        print("--- Imports: OK")

        # 2. Test Vault (Verifica crittografia)
        v = Vault()
        test_payload = {"status": "testing"}
        v.encrypt_data(test_payload)
        if v.decrypt_data().get("status") == "testing":
            print("--- Vault Security: OK")
        else:
            raise Exception("Vault decryption mismatch")
        
        # 3. Test Struttura Classi (Verifica se launch_browser esiste)
        # Passiamo None come controller per il test statico
        executor = DomExecutorPlaywright(None)
        if hasattr(executor, 'launch_browser'):
            print("--- Class Structure: OK")
        else:
            print("--- ERROR: launch_browser() is missing in DomExecutorPlaywright!")
            sys.exit(1)

        print(">>> SUCCESS: ALL TESTS PASSED")
        sys.exit(0)

    except Exception as e:
        print(f"--- CRITICAL ERROR: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    run_tests()
