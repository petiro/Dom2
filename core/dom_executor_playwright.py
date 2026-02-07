import os
import sys
import time
import random
import math
import getpass
import platform
import subprocess
from playwright.sync_api import sync_playwright

# --- FUNZIONI HELPER PER IL COMPORTAMENTO UMANO ---

def human_delay(min_s=0.5, max_s=1.5):
    """Simula l'esitazione umana tra un'azione e l'altra."""
    time.sleep(random.uniform(min_s, max_s))

def human_move_to_element(page, element):
    """
    Muove il mouse verso l'elemento con traiettoria fluida e jitter casuale.
    Usa il parametro 'steps' di Playwright per simulare il movimento naturale.
    """
    box = element.bounding_box()
    if not box:
        return None, None
    
    # Calcola il centro dell'elemento con un leggero jitter casuale (offset)
    # per evitare di cliccare sempre lo stesso pixel esatto.
    target_x = box['x'] + box['width'] / 2 + random.uniform(-5, 5)
    target_y = box['y'] + box['height'] / 2 + random.uniform(-5, 5)
    
    # Il parametro 'steps' scompone il movimento in micro-spostamenti simulando la mano umana
    page.mouse.move(target_x, target_y, steps=random.randint(15, 35))
    return target_x, target_y

def close_chrome():
    """Kill all Chrome processes to free the user profile for Playwright persistent context."""
    try:
        if platform.system() == "Windows":
            subprocess.run(["taskkill", "/F", "/IM", "chrome.exe"],
                           capture_output=True, timeout=5)
        else:
            subprocess.run(["pkill", "-f", "chrome"], capture_output=True, timeout=5)
        time.sleep(1)
    except Exception:
        pass


def _detect_chrome_path():
    """Auto-detect Chrome executable path based on OS."""
    if platform.system() == "Windows":
        candidates = [
            os.path.join(os.environ.get("PROGRAMFILES", ""), "Google", "Chrome", "Application", "chrome.exe"),
            os.path.join(os.environ.get("PROGRAMFILES(X86)", ""), "Google", "Chrome", "Application", "chrome.exe"),
            os.path.join(os.environ.get("LOCALAPPDATA", ""), "Google", "Chrome", "Application", "chrome.exe"),
        ]
    elif platform.system() == "Darwin":
        candidates = ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"]
    else:
        candidates = ["/usr/bin/google-chrome", "/usr/bin/chromium-browser", "/usr/bin/chromium"]

    for path in candidates:
        if path and os.path.exists(path):
            return path
    return None


def _detect_chrome_profile():
    """Auto-detect Chrome user data directory based on OS."""
    user = getpass.getuser()
    if platform.system() == "Windows":
        return os.path.join(os.environ.get("LOCALAPPDATA", f"C:\\Users\\{user}\\AppData\\Local"),
                            "Google", "Chrome", "User Data")
    elif platform.system() == "Darwin":
        return os.path.expanduser("~/Library/Application Support/Google/Chrome")
    else:
        return os.path.expanduser("~/.config/google-chrome")


class DomExecutorPlaywright:
    """
    DOM Executor using Playwright for browser automation.
    Enterprise-grade Stealth version: Human movements, WebDriver bypass, Smart Waits.
    """

    MAX_RETRIES = 3
    RETRY_DELAY = 2

    def __init__(self, logger, headless=False, allow_place=False, pin="0503",
                 chrome_profile="Default", use_real_chrome=True):
        self.logger = logger
        self.allow_place = allow_place
        self.pin = pin
        self.headless = headless
        self.chrome_profile = chrome_profile
        self.use_real_chrome = use_real_chrome

        self.pw = None
        self.browser = None
        self.ctx = None
        self.page = None
        self.last_login_time = 0
        self._initialized = False
        self.healer = None

    def _ensure_browser(self):
        """Initialize browser with Stealth arguments and WebDriver bypass."""
        if self._initialized:
            return True

        try:
            self.pw = sync_playwright().start()

            chrome_path = _detect_chrome_path() if self.use_real_chrome else None
            chrome_profile_dir = _detect_chrome_profile() if self.use_real_chrome else None

            # Argomenti Stealth Avanzati
            stealth_args = [
                "--disable-blink-features=AutomationControlled",
                "--no-default-browser-check",
                "--start-maximized",
                "--disable-infobars"
            ]

            if chrome_path and chrome_profile_dir and os.path.exists(chrome_profile_dir):
                self.logger.info(f"Using real Chrome: {chrome_path}")

                self.ctx = self.pw.chromium.launch_persistent_context(
                    chrome_profile_dir,
                    executable_path=chrome_path,
                    headless=False,
                    viewport=None,   # Fondamentale per fingerprint reale
                    no_viewport=True,
                    args=[f"--profile-directory={self.chrome_profile}"] + stealth_args,
                    locale="it-IT",
                    timezone_id="Europe/Rome",
                )
                self.browser = None

                if self.ctx.pages:
                    self.page = self.ctx.pages[0]
                else:
                    self.page = self.ctx.new_page()

                # BYPASS navigator.webdriver (Iniezione JavaScript)
                self.page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

                self.logger.info("Real Chrome initialized with Stealth Patches")
            else:
                if self.use_real_chrome:
                    self.logger.warning("Chrome not found, falling back to standalone Chromium")

                self.browser = self.pw.chromium.launch(headless=self.headless, args=stealth_args)
                self.ctx = self.browser.new_context(
                    viewport={"width": 1366, "height": 768},
                    locale="it-IT",
                    timezone_id="Europe/Rome",
                )
                self.page = self.ctx.new_page()
                
                # Bypass WebDriver anche su Chromium standalone
                self.page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
                self.logger.info("Standalone Chromium initialized with Stealth Patches")

            self._initialized = True
            return True

        except Exception as e:
            self.logger.error(f"Failed to initialize browser: {e}")
            return False

    def place_bet(self, selectors):
        """Place a bet using Human-Style interaction (Mouse movements + Split Click)."""
        if not self.allow_place:
            self.logger.warning("BETS ARE DISABLED (allow_place=False). Skipping.")
            return False

        if not self._ensure_browser():
            return False

        try:
            btn_selector = selectors.get('bet_button', 'button:has-text("Piazza")')
            btn = self.page.locator(btn_selector)
            btn.wait_for(state="visible", timeout=7000)

            # --- LOGICA GHOST MODE ---
            self.logger.info("Simulating human movement to bet button...")
            
            # 1. Delay di esitazione pre-movimento
            human_delay(0.6, 1.3)
            
            # 2. Movimento fluido verso l'elemento
            x, y = human_move_to_element(self.page, btn)
            
            if x and y:
                # 3. Micro-esitazione pre-click (occhi puntati sul tasto)
                human_delay(0.2, 0.5)
                
                # 4. Click umano: down -> micro-pausa -> up
                self.page.mouse.down()
                time.sleep(random.uniform(0.06, 0.18)) # Tempo di pressione fisica
                self.page.mouse.up()
                
                self.logger.info("BET PLACED SUCCESSFULLY (Human Interaction)!")
                return True
            
            return False
        except Exception as e:
            self.logger.error(f"Failed to place bet: {e}")
            return False

    # ... (Resto dei metodi come _wait_for_page_ready, navigate_to_match, select_market) ...
    # Assicurati di usare human_delay() e human_move_to_element() 
    # anche in navigate_to_match e select_market per coerenza totale.

    def close(self):
        """Clean up browser resources."""
        self.logger.info("Closing browser...")
        try:
            if self.ctx: self.ctx.close()
            if self.browser: self.browser.close()
            if self.pw: self.pw.stop()
        except: pass
        self.logger.info("Browser closed")
