"""
OS Human Interaction — Desktop-level automation via PyAutoGUI.

Provides:
  - Chrome icon detection and double-click from desktop
  - Fallback via Windows Start menu search
  - Human-like URL navigation via keyboard (Ctrl+L)
  - Window minimize/restore for desktop access

Requires: pip install pyautogui opencv-python
Note: PyAutoGUI requires display access (not for headless VPS without virtual display).
"""
import time
import random
import os
import platform

# --- 🛡️ SAFETY LOCK (KILL SWITCH) 🛡️ ---
# Imposta su True SOLO se il bot gira su un PC dedicato/VM dove non muovi il mouse.
# Se False, tutte le funzioni che rubano il controllo del mouse/tastiera sono DISABILITATE.
SAFE_OS_AUTOMATION = False  

try:
    import pyautogui
    pyautogui.FAILSAFE = True  # Move mouse to corner to abort
    PYAUTOGUI_AVAILABLE = True
except ImportError:
    PYAUTOGUI_AVAILABLE = False


class HumanOS:
    """Desktop-level human interaction using PyAutoGUI.
    
    V5 UPDATE: Protected by SAFE_OS_AUTOMATION flag.
    If flag is False, this class becomes inert (safe mode).
    """

    def __init__(self, logger):
        self.logger = logger
        if not PYAUTOGUI_AVAILABLE:
            self.logger.warning("[HumanOS] PyAutoGUI not installed — desktop interaction disabled")
        
        # Log dello stato di sicurezza all'avvio
        if not SAFE_OS_AUTOMATION:
            self.logger.warning("[HumanOS] 🛡️ SAFETY LOCK ATTIVO: Automazione Desktop DISABILITATA per sicurezza.")

    @property
    def available(self) -> bool:
        # Se la safety è attiva (False), risultiamo "non disponibili" al Controller
        return PYAUTOGUI_AVAILABLE and SAFE_OS_AUTOMATION

    def open_browser_from_desktop(self, icon_path="data/chrome_icon.png"):
        """Simulate opening Chrome by finding and double-clicking the desktop icon."""
        if not self.available:
            self.logger.info("[HumanOS] Skipped open_browser (Safety Lock Active)")
            return False

        if not PYAUTOGUI_AVAILABLE:
            self.logger.warning("[HumanOS] PyAutoGUI not available, skipping desktop interaction")
            return False

        self.logger.info("[HumanOS] Looking for browser icon on desktop...")

        try:
            # 1. Show desktop (Win+D)
            pyautogui.hotkey('win', 'd')
            time.sleep(1.5)

            # 2. Try to find icon visually
            icon_abs = os.path.abspath(icon_path)
            if os.path.exists(icon_abs):
                try:
                    location = pyautogui.locateOnScreen(icon_abs, confidence=0.8)
                    if location:
                        x, y = pyautogui.center(location)
                        self.logger.info(f"[HumanOS] Icon found at ({x}, {y}). Double-clicking...")
                        pyautogui.moveTo(x, y, duration=random.uniform(0.5, 1.0))
                        time.sleep(random.uniform(0.2, 0.5))
                        pyautogui.doubleClick()
                        time.sleep(3)
                        return True
                    else:
                        self.logger.warning("[HumanOS] Icon not found on screen")
                except Exception as e:
                    self.logger.warning(f"[HumanOS] Visual search failed: {e}")
            else:
                self.logger.info(f"[HumanOS] Icon file not found: {icon_abs}")

            # 3. Fallback: Start menu search
            self.logger.info("[HumanOS] Trying Start menu fallback...")
            return self._start_menu_fallback()
            
        except Exception as e:
            self.logger.error(f"[HumanOS] Critical Error in desktop interaction: {e}")
            return False

    def _start_menu_fallback(self):
        """Open Chrome via Windows Start menu search."""
        if not self.available: 
            return False
            
        try:
            pyautogui.press('win')
            time.sleep(0.8)
            # Type "chrome" with human rhythm
            for char in "chrome":
                pyautogui.write(char)
                time.sleep(random.uniform(0.05, 0.15))
            time.sleep(1.0)
            pyautogui.press('enter')
            time.sleep(3)
            self.logger.info("[HumanOS] Chrome launched via Start menu")
            return True
        except Exception as e:
            self.logger.error(f"[HumanOS] Start menu fallback failed: {e}")
            return False

    def human_navigate(self, url):
        """Navigate to URL by clicking address bar (Ctrl+L) and typing."""
        if not self.available:
            self.logger.info("[HumanOS] Skipped human_navigate (Safety Lock Active)")
            return False

        self.logger.info(f"[HumanOS] Navigating to: {url}")

        try:
            # Focus address bar
            pyautogui.hotkey('ctrl', 'l')
            time.sleep(0.5)

            # Type URL with human rhythm
            for char in url:
                pyautogui.write(char)
                time.sleep(random.uniform(0.03, 0.12))

            time.sleep(0.3)
            pyautogui.press('enter')
            return True
        except Exception as e:
            self.logger.error(f"[HumanOS] Navigation error: {e}")
            return False

    def minimize_all(self):
        """Minimize all windows to show desktop."""
        if not self.available:
            return
        try:
            pyautogui.hotkey('win', 'd')
            time.sleep(1)
        except Exception:
            pass

    def kill_chrome_processes(self):
        """Kill all Chrome processes via OS command (SAFE TO KEEP ACTIVE)."""
        # Questo metodo è sicuro perché usa comandi OS, non mouse/tastiera.
        # Lo lasciamo attivo anche con il Safety Lock.
        try:
            if platform.system() == "Windows":
                import subprocess
                subprocess.run(["taskkill", "/F", "/IM", "chrome.exe"],
                               capture_output=True, timeout=5)
            self.logger.info("[HumanOS] Chrome processes killed")
        except Exception as e:
            self.logger.warning(f"[HumanOS] Kill Chrome failed: {e}")
