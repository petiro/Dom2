import sys
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("CI_VERIFIER")

def run_tests():
    print(">>> STARTING STATIC INTEGRITY CHECK")

    try:  
        # 1. Test Vault  
        from core.security import Vault  
        v = Vault()  
        print("[OK] Vault Structure")  

        # 2. Test Browser Engine (Caricamento classi)  
        from core.dom_executor_playwright import DomExecutorPlaywright  
        
        # Inizializziamo l'app Qt (necessaria per i segnali se presenti nel progetto)
        # Import protetto per ambiente CI
        try:
            from PySide6.QtWidgets import QApplication
            app = QApplication.instance() or QApplication(sys.argv)
        except ImportError:
            pass # CI Environment senza PySide6 GUI
          
        # Verifichiamo che la classe si istanzi senza errori  
        test_logger = logging.getLogger("TEST_EXECUTOR")  
        executor = DomExecutorPlaywright(test_logger)  
        print("[OK] DomExecutor Instantiation")  

        # Verifica presenza metodi critici  
        methods = ['launch_browser', 'close', 'recycle_browser']  
        for m in methods:  
            if not hasattr(executor, m):  
                raise Exception(f"Missing critical method: {m}")  
        print("[OK] Method Mapping")  

        print(">>> INTEGRITY CHECK PASSED - READY FOR BUILD")  
        sys.exit(0)  

    except Exception as e:  
        print(f"[FAIL] INTEGRITY CHECK FAILED: {str(e)}")  
        sys.exit(1)

if __name__ == "__main__":
    run_tests()