import time
import threading
import logging
import re
import os
import yaml
from playwright.sync_api import sync_playwright

from core.human_mouse import HumanMouse
from core.config_paths import TIMEOUT_MEDIUM, CONFIG_DIR
from core.anti_detect import STEALTH_INJECTION_V4

# FIX CIRCULAR IMPORT: Importiamo il modulo intero, non la classe
import core.dom_self_healing 

class DomExecutorPlaywright:
    def __init__(self, logger=None, headless=False, allow_place=False, **kwargs):
        self.logger = logger or logging.getLogger("Executor")
        self.headless = headless
        self.allow_place = allow_place

        self.pw = None
        self.browser = None
        self.page = None
        self.mouse = None

        self._internal_lock = threading.RLock() 
        self._initialized = False

        # FIX: Istanziazione tramite modulo
        self.healer = core.dom_self_healing.DOMSelfHealing(self)
        self._heal_attempts = 0

    def launch_browser(self):
        with self._internal_lock:
            try:
                if self._initialized and self.page and not self.page.is_closed():
                    return True

                if not self.pw:
                    self.pw = sync_playwright().start()

                self.browser = self.pw.chromium.launch(
                    headless=self.headless,
                    args=["--disable-blink-features=AutomationControlled"]
                )

                self.page = self.browser.new_page()
                self.page.add_init_script(STEALTH_INJECTION_V4)

                self.mouse = HumanMouse(self.page, self.logger)
                self._initialized = True
                return True

            except Exception as e:
                self.logger.error(f"Browser launch fail: {e}")
                return False

    def _health_check(self):
        try:
            if not self.page: return False
            self.page.title()
            return True
        except: return False

    def _smart_locate(self, key, selector):
        if not self.page: return None

        if self._heal_attempts > 2:
            self.logger.error("Healing limit reached.")
            return None

        try:
            loc = self.page.locator(selector).first
            loc.wait_for(state="visible", timeout=2000)
            self._heal_attempts = 0
            return loc
        except:
            self._heal_attempts += 1
            new_sel = self.healer.heal(key)
            if new_sel:
                return self._smart_locate(key, new_sel)
            return None

    def verify_bet_success(self, teams=None):
        if not self.allow_place: return True
        try:
            self.page.wait_for_timeout(2000)
            txt = self.page.inner_text("body")[:4000].lower()

            if "non accett" in txt or "rifiutat" in txt or "errore" in txt:
                return False

            success_keys = ["scommessa accettata", "bet placed", "successfully placed", "ricevuta", "codice"]
            if any(k in txt for k in success_keys):
                return True
            return False
        except: return False

    def click(self, key, selector):
        with self._internal_lock:
            try:
                if not self.launch_browser(): return False
                if not self._health_check():
                    self.logger.warning("Browser dead. Restart.")
                    self.recycle_browser()

                loc = self._smart_locate(key, selector)
                if not loc:
                    self.logger.error(f"Element not found: {key}")
                    return False

                if self.mouse: self.mouse.click_locator(loc)
                else: loc.click()
                return True
            except Exception as e:
                self.logger.error(f"Click error: {e}")
                return False

    def ensure_login(self): return True
    def navigate_to_match(self, t): return self.launch_browser()
    def find_odds(self, t, m): return 1.5
    def place_bet(self, t, m, s): return True
    
    def close(self):
        try:
            if self.browser: self.browser.close()
        except: pass

    def recycle_browser(self):
        self.close()
        self._initialized = False
        self.launch_browser()