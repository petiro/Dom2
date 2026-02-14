import time
import os
import logging
try:
    import pyautogui
    PYAUTOGUI_AVAILABLE = True
except ImportError:
    PYAUTOGUI_AVAILABLE = False

class HumanInteraction:
    def __init__(self, logger=None):
        self.logger = logger or logging.getLogger("SuperAgent")
        if PYAUTOGUI_AVAILABLE:
            pyautogui.FAILSAFE = True # Sposta il mouse nell'angolo in alto a sx per stoppare
    
    def open_chrome_from_desktop(self):
        """
        Usa il mouse per cliccare l'icona di Chrome sul Desktop.
        Utile se vuoi automatizzare l'apertura del collegamento con porta 9222.
        """
        if not PYAUTOGUI_AVAILABLE:
            self.logger.warning("PyAutoGUI non installato. Impossibile interagire col desktop.")
            return False

        self.logger.info("🖱️ HUMAN: Cerco icona Chrome sul desktop...")
        
        # Minimizza tutte le finestre (Mostra Desktop)
        pyautogui.hotkey('win', 'd')
        time.sleep(1)

        try:
            # Cerca l'immagine dell'icona (devi avere chrome_icon.png nella cartella data)
            # Se non hai l'immagine, questo fallisce.
            icon_path = os.path.join("data", "chrome_icon.png")
            
            if os.path.exists(icon_path):
                location = pyautogui.locateOnScreen(icon_path, confidence=0.8)
                if location:
                    pyautogui.doubleClick(location)
                    self.logger.info("🖱️ Click su Chrome effettuato.")
                    time.sleep(3) # Tempo di apertura
                    return True
            
            self.logger.warning("⚠️ Icona Chrome non trovata a video.")
            return False
            
        except Exception as e:
            self.logger.error(f"Errore PyAutoGUI: {e}")
            return False

    def wake_up_screen(self):
        """Muove leggermente il mouse per evitare lo standby"""
        if PYAUTOGUI_AVAILABLE:
            pyautogui.moveRel(1, 0)
            pyautogui.moveRel(-1, 0)
