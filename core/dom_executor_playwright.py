import os
import sys
import time
import base64
import random
from playwright.sync_api import sync_playwright
from core.ai_selector_validator import validate_selector
from core.anti_detect import STEALTH_INJECTION_V4

class DomExecutorPlaywright:
    def __init__(self, logger, headless=False, allow_place=False, pin=None,
                 chrome_profile="Default", use_real_chrome=True):
        self.logger = logger
        self.headless = headless
        self.pin = pin
        self.use_real_chrome = use_real_chrome
        self.pw = None
        self.browser = None
        self.ctx = None 
        self.page = None
        self._initialized = False
        self.selector_file = "selectors.yaml"

    def launch_browser(self):
        if self._initialized: return True
        try:
            self.pw = sync_playwright().start()
            args = ["--disable-blink-features=AutomationControlled", "--start-maximized"]
            
            # Setup Browser
            self.browser = self.pw.chromium.launch(headless=self.headless, args=args)
            
            # Setup Context
            self.ctx = self.browser.new_context(viewport={"width": 1366, "height": 768})
            self.page = self.ctx.new_page()
            
            # Injection
            self.page.add_init_script(STEALTH_INJECTION_V4)
            
            self._initialized = True
            return True
        except Exception as e:
            self.logger.error(f"Browser Init Error: {e}")
            return False

    def close(self):
        """Cleanup completo risorse per evitare Memory Leak."""
        try:
            if self.page: self.page.close()
        except: pass
        
        try:
            # ✅ FIX: Chiusura Context esplicita
            if self.ctx: self.ctx.close()
        except: pass
        
        try:
            if self.browser: self.browser.close()
        except: pass
        
        try:
            if self.pw: self.pw.stop()
        except: pass
        
        self._initialized = False
        self.page = None
        self.ctx = None
        self.browser = None
        self.pw = None

    def _safe_click(self, selector, timeout=5000):
        # ✅ Validazione selector
        if not validate_selector(selector):
            self.logger.warning(f"Blocked unsafe selector: {selector}")
            return False

        try:
            loc = self.page.locator(selector).first
            loc.wait_for(state="visible", timeout=timeout)
            loc.click()
            return True
        except Exception:
            return False

    def _safe_fill(self, selector, text, timeout=5000):
        if not validate_selector(selector): return False
        try:
            loc = self.page.locator(selector).first
            loc.wait_for(state="visible", timeout=timeout)
            loc.fill(text)
            return True
        except: return False

    def ensure_login(self, selectors):
        if not self.launch_browser(): return False
        
        # Logica Login semplificata
        login_btn = selectors.get("login_btn", "text=Login")
        
        if self.pin:
            pass # Qui logica futura inserimento PIN
            
        if self._safe_click(login_btn):
            return True
        return False

    def navigate_to_match(self, teams, selectors):
        if not self.launch_browser(): return False
        # Stub navigazione
        return True

    def place_bet(self, teams, market, stake):
        self.logger.info(f"💰 Betting {stake} on {teams}")
        return True

    def _load_selectors(self):
        import yaml
        try:
            with open(f"config/{self.selector_file}", "r") as f:
                return yaml.safe_load(f)
        except: return {}

    def set_selector_file(self, f): self.selector_file = f
    def check_health(self): return self.page and not self.page.is_closed()
    
    # Stubs
    def set_trainer(self, t): pass
    def set_healer(self, h): pass
    def recover_session(self): self.close(); self.launch_browser()
    def take_screenshot_b64(self): return ""
    def get_dom_snapshot(self): return ""
