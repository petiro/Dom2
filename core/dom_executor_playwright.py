import time
import random
import threading
import logging
import yaml
import re
from playwright.sync_api import sync_playwright
from core.anti_detect import STEALTH_INJECTION_V4
from core.human_mouse import HumanMouse
from core.config_paths import CONFIG_DIR, TIMEOUT_SHORT, TIMEOUT_MEDIUM, TIMEOUT_LONG

class DomExecutorPlaywright:
    def __init__(self, logger=None, headless=False, allow_place=False, pin=None, use_real_chrome=True, **kwargs):
        self.logger = logger or logging.getLogger(self.__class__.__name__)
        self.headless = headless
        self.allow_place = allow_place
        self.use_real_chrome = use_real_chrome
        self.pw = None
        self.browser = None
        self.ctx = None
        self.page = None
        self._initialized = False
        self.selector_file = "selectors.yaml"
        self.human = None
        self.mouse = None
        self._internal_lock = threading.Lock()

    def set_live_mode(self, enabled: bool):
        self.allow_place = enabled
        self.logger.warning(f"🔧 Executor impostato su: {enabled}")

    def launch_browser(self):
        if self._initialized and self.page and not self.page.is_closed(): return True
        self.logger.info("🌐 Inizializzazione Playwright...")
        try:
            if not self.pw: self.pw = sync_playwright().start()
            
            try:
                self.browser = self.pw.chromium.connect_over_cdp("http://localhost:9222")
                self.ctx = self.browser.contexts[0]
                self.page = self.ctx.pages[0] if self.ctx.pages else self.ctx.new_page()
                self.logger.info("✅ Agganciato a Chrome esistente.")
            except Exception:
                self.logger.info("ℹ️ Avvio nuova istanza Chrome...")
                args = ["--disable-blink-features=AutomationControlled", "--start-maximized"]
                channel = "chrome" if self.use_real_chrome else "chromium"
                self.browser = self.pw.chromium.launch(headless=self.headless, channel=channel, args=args)
                self.ctx = self.browser.new_context(viewport={"width": 1920, "height": 1080})
                self.page = self.ctx.new_page()

            self.page.add_init_script(STEALTH_INJECTION_V4)
            self.mouse = HumanMouse(self.page, self.logger)
            self._initialized = True
            return True
        except Exception as e:
            self.logger.critical(f"❌ Errore browser: {e}")
            self.close()
            return False

    def close(self):
        try:
            if self.browser: self.browser.close()
            if self.pw: self.pw.stop()
        except: pass
        finally:
            self._initialized = False
            self.pw = None
            self.browser = None

    def _load_selectors(self):
        import os
        try:
            with open(os.path.join(CONFIG_DIR, self.selector_file), "r") as f:
                return yaml.safe_load(f) or {}
        except: return {}

    def click(self, selector_or_locator, timeout=TIMEOUT_MEDIUM):
        with self._internal_lock:
            try:
                if isinstance(selector_or_locator, str):
                    if not self.launch_browser(): return False
                    loc = self.page.locator(selector_or_locator).first
                else:
                    loc = selector_or_locator
                
                loc.wait_for(state="visible", timeout=timeout)
                if self.mouse: return self.mouse.click_locator(loc)
                else:
                    loc.click()
                    return True
            except: return False

    def human_fill(self, selector, text):
        if not self.launch_browser(): return False
        if self.click(selector, timeout=TIMEOUT_SHORT):
            try:
                self.page.locator(selector).first.fill("")
                for char in str(text):
                    self.page.keyboard.type(char)
                    time.sleep(random.uniform(0.04, 0.12))
                return True
            except: pass
        return False

    def ensure_login(self, selectors=None):
        if selectors is None: selectors = self._load_selectors()
        if not self.launch_browser(): return False
        
        bal = selectors.get("balance_element")
        if bal:
            try: 
                if self.page.locator(bal).first.is_visible(timeout=TIMEOUT_SHORT): return True
            except: pass
            
        btn = selectors.get("login_button")
        if btn:
            self.click(btn)
            return True
        return False

    def verify_bet_success(self, teams=None, selectors=None):
        if not self.allow_place: return True
        if selectors is None: selectors = self._load_selectors()
        
        try:
            msg = selectors.get("success_message", "Scommessa accettata")
            self.page.wait_for_selector(f"text={msg}", timeout=TIMEOUT_LONG)
            return True
        except:
            try:
                content = self.page.content().lower()
                if re.search(r"(accettat|success|bet placed)", content): return True
            except: pass
            return False

    def navigate_to_match(self, teams, selectors=None):
        if not teams: return False
        if selectors is None: selectors = self._load_selectors()
        box = selectors.get("search_box")
        if not self.human_fill(box, teams): return False
        self.page.keyboard.press("Enter")
        res = selectors.get("match_result", ".match-row")
        try:
            self.page.wait_for_selector(res, timeout=TIMEOUT_MEDIUM)
            return self.click(res)
        except: return False

    def place_bet(self, teams, market, stake):
        if not self.allow_place: return True
        sels = self._load_selectors()
        if not self.human_fill(sels.get("stake_input"), str(stake)): return False
        if self.mouse: self.mouse.idle_behavior()
        return self.click(sels.get("place_button"))

    def find_odds(self, match, market):
        return 2.0 

    def scan_page_elements(self, url):
        return []