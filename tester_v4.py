import sys
import os
import time
import threading
import logging
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QObject

# Configura Logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - TEST - %(message)s')
logger = logging.getLogger("CI_RUNNER")

def run_tests():
    print("🚀 AVVIO TEST AUTOMATICO V4 (CI MODE)...")
    
    try:
        # 1. TEST IMPORTAZIONI
        logger.info("Checking Imports...")
        from core.security import Vault
        from core.dom_executor_playwright import DomExecutorPlaywright
        # Se passa qui, le dipendenze sono OK
        print("   ✅ Imports: PASS")

        # 2. TEST VAULT (Hardware Binding simulato)
        logger.info("Checking Vault...")
        vault = Vault()
        # Su GitHub Actions l'hardware ID cambierà ogni volta, 
        # ma il test verifica che la crittografia funzioni senza crashare.
        data = {"test": "ok"}
        vault.encrypt_data(data)
        decrypted = vault.decrypt_data()
        if decrypted.get("test") == "ok":
            print("   ✅ Vault Crypto: PASS")
        else:
            raise Exception("Vault Decryption Failed")

        # 3. TEST PLAYWRIGHT (Browser)
        logger.info("Checking Browser Engine...")
        
        # Mock del Controller per intercettare i segnali
        class MockController(QObject):
            def safe_emit(self, signal, *args):
                pass # Ignora i segnali UI
        
        # Istanzia l'executor
        executor = DomExecutorPlaywright(MockController())
        
        # Avvia il browser in un thread separato
        t = threading.Thread(target=executor._ensure_browser, daemon=True)
        t.start()
        
        # Attesa attiva (Polling) max 15 secondi
        for _ in range(15):
            if executor.page:
                break
            time.sleep(1)
            
        if executor.page:
            print("   ✅ Browser Launch: PASS")
            
            # Navigazione Test
            executor.page.goto("https://example.com")
            if "Example Domain" in executor.page.title():
                print("   ✅ Navigation: PASS")
            else:
                print("   ⚠️ Navigation Title Mismatch (Non critico)")
            
            # Memory Check
            mem = executor.memory_check()
            print(f"   ✅ Memory Check: {mem:.2f} MB")
            
            executor.close()
        else:
            raise Exception("Browser failed to launch in 15s")

        print("-" * 30)
        print("🎉 TUTTI I TEST PASSATI CON SUCCESSO")
        sys.exit(0) # Exit code 0 = Successo per GitHub Actions

    except Exception as e:
        print(f"❌ TEST FALLITO: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1) # Exit code 1 = Fallimento per GitHub Actions

if __name__ == "__main__":
    # Necessario per inizializzare i timer e i thread Qt
    app = QApplication(sys.argv)
    run_tests()
