import sys
import os
import time
import threading
import logging
from PySide6.QtWidgets import QApplication

# Configurazione Log per CI
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("CI_RUNNER")

class MockController:
    def safe_emit(self, *args): pass
    def info(self, msg): logger.info(msg)
    def error(self, msg): logger.error(msg)
    def warning(self, msg): logger.warning(msg)

def run_tests():
    print(">>> STARTING FINAL INTEGRITY CHECK")
    # Forza Headless per GitHub
    os.environ["PLAYWRIGHT_HEADLESS"] = "1"
    
    try:
        from core.security import Vault
        from core.dom_executor_playwright import DomExecutorPlaywright
        
        # Test Vault
        v = Vault()
        print("✅ Vault Logic: OK")

        # Test Browser Engine
        app = QApplication.instance() or QApplication(sys.argv)
        executor = DomExecutorPlaywright(MockController())
        
        # Avviamo il browser in un thread
        t = threading.Thread(target=executor.launch_browser, daemon=True)
        t.start()
        
        # Polling per 15 secondi
        for _ in range(15):
            if executor.page:
                print("✅ Browser Engine: OK")
                executor.close()
                sys.exit(0)
            time.sleep(1)
            
        raise Exception("Browser initialization timeout")

    except Exception as e:
        print(f"❌ TEST FAILED: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    run_tests()
