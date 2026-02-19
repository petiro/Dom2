import time
import os
import logging
from core.utils import get_project_root

try:
    import pyautogui
    PYAUTOGUI_AVAILABLE = True
except ImportError:
    PYAUTOGUI_AVAILABLE = False

class HumanInteraction:
    def __init__(self, logger=None):
        self.logger = logger or logging.getLogger("SuperAgent")
        if PYAUTOGUI_AVAILABLE:
            pyautogui.FAILSAFE = True

    def open_chrome_from_desktop(self):
        if not PYAUTOGUI_AVAILABLE:
            self.logger.warning("PyAutoGUI non installato. Impossibile interagire col desktop.")
            return False

        self.logger.info("🖱️ HUMAN: Cerco icona Chrome sul desktop...")

        pyautogui.hotkey('win', 'd')
        time.sleep(1)

        try:
            icon_path = os.path.join(get_project_root(), "data", "chrome_icon.png")

            if os.path.exists(icon_path):
                location = pyautogui.locateOnScreen(icon_path, confidence=0.8)
                if location:
                    pyautogui.doubleClick(location)
                    self.logger.info("🖱️ Click su Chrome effettuato.")
                    time.sleep(3)
                    return True

            self.logger.warning("⚠️ Icona Chrome non trovata a video.")
            return False

        except Exception as e:
            self.logger.error("Errore PyAutoGUI: %s", e)
            return False

    def wake_up_screen(self):
        if PYAUTOGUI_AVAILABLE:
            pyautogui.moveRel(1, 0)
            pyautogui.moveRel(-1, 0)