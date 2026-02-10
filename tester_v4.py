import sys
import os
import logging
from PySide6.QtWidgets import QApplication

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("CI_VERIFIER")

def run_tests():
    print(">>> STARTING STATIC INTEGRITY CHECK")
    
    try:
        # 1. Test Vault
        from core.security import Vault
        v = Vault()
        print("✅ Vault Structure: OK")

        # 2. Test Browser Engine (Caricamento classi)
        from core.dom_executor_playwright import DomExecutorPlaywright
        
        # Inizializziamo l'app Qt (necessaria per i segnali)
        app = QApplication.instance() or QApplication(sys.argv)
        
        # Verifichiamo che la classe si istanzi senza errori
        import logging
        test_logger = logging.getLogger("TEST_EXECUTOR")
        executor = DomExecutorPlaywright(test_logger)
        print("✅ DomExecutor Instantiation: OK")

        # Verifica presenza metodi critici
        methods = ['launch_browser', 'close', 'recycle_browser']
        for m in methods:
            if not hasattr(executor, m):
                raise Exception(f"Missing critical method: {m}")
        print("✅ Method Mapping: OK")

        print(">>> INTEGRITY CHECK PASSED - READY FOR BUILD")
        sys.exit(0)

    except Exception as e:
        print(f"❌ INTEGRITY CHECK FAILED: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    run_tests()
