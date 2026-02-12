"""
OS Human Interaction — Desktop-level automation via PyAutoGUI.
SAFE MODE: DISABILITATO PER EVITARE CLICK RANDOM E CHIUSURE CHROME.
"""
import time
import random
import os
import platform

# --- 🛡️ SAFETY LOCK (KILL SWITCH) 🛡️ ---
# Impostato su False per bloccare qualsiasi automazione OS pericolosa.
# Il bot userà SOLO Playwright (Browser interno).
SAFE_OS_AUTOMATION = False  

try:
    import pyautogui
    # Fail-safe: sposta il mouse nell'angolo per abortire (se attivo)
    pyautogui.FAILSAFE = True  
    PYAUTOGUI_AVAILABLE = True
except ImportError:
    PYAUTOGUI_AVAILABLE = False


class HumanOS:
    """
    Gestore interazione OS.
    V5 UPDATE: Completamente neutralizzato dal flag SAFE_OS_AUTOMATION = False.
    Serve solo per funzioni sicure (es. taskkill) o come placeholder.
    """

    def __init__(self, logger):
        self.logger = logger
        if not PYAUTOGUI_AVAILABLE:
            self.logger.warning("[HumanOS] PyAutoGUI not installed.")
        
        # Logghiamo chiaramente che il modulo è disattivato
        if not SAFE_OS_AUTOMATION:
            self.logger.warning("[HumanOS] 🛡️ SAFETY LOCK ATTIVO: Automazione Mouse/Tastiera DISABILITATA.")

    @property
    def available(self) -> bool:
        # Il Controller controllerà questo. Se False, non tenterà fallback strani.
        return PYAUTOGUI_AVAILABLE and SAFE_OS_AUTOMATION

    def open_browser_from_desktop(self, icon_path="data/chrome_icon.png"):
        """Tenta di aprire Chrome dal desktop (DISABILITATO)."""
        if not self.available:
            self.logger.info("[HumanOS] Skipped open_browser (Safety Lock Active)")
            return False
        
        # ... codice legacy rimosso logicamente dal lock ...
        return False

    def human_navigate(self, url):
        """Navigazione via barra indirizzi (DISABILITATA)."""
        if not self.available:
            self.logger.info("[HumanOS] Skipped human_navigate (Safety Lock Active)")
            return False
        return False

    def minimize_all(self):
        """Minimizza finestre (DISABILITATO)."""
        if not self.available:
            return

    def kill_chrome_processes(self):
        """
        Termina i processi Chrome via comando OS.
        QUESTO È SICURO: Non usa il mouse, ma comandi di sistema.
        Lo lasciamo attivo per pulire la RAM in caso di crash.
        """
        try:
            if platform.system() == "Windows":
                import subprocess
                subprocess.run(["taskkill", "/F", "/IM", "chrome.exe"],
                               capture_output=True, timeout=5)
            self.logger.info("[HumanOS] Chrome processes killed via taskkill (Safe Operation)")
        except Exception as e:
            self.logger.warning(f"[HumanOS] Kill Chrome failed: {e}")
