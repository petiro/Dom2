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
        
        # Questa variabile decide se piazzare o no (Default = False/Demo)
        self.allow_place = allow_place 
        
        self.pw = None
        self.browser = None
        self.ctx = None 
        self.page = None
        self._initialized = False
        self.selector_file = "selectors.yaml"

    def set_live_mode(self, enabled: bool):
        """Abilita o disabilita il piazzamento reale."""
        self.allow_place = enabled
        mode = "LIVE" if enabled else "DEMO"
        self.logger.warning(f"🔧 Executor impostato su: {mode}")

    def launch_browser(self):
        if self._initialized: return True
        try:
            self.pw = sync_playwright().start()
            args = ["--disable-blink-features=AutomationControlled", "--start-maximized"]
            self.browser = self.pw.chromium.launch(headless=self.headless, args=args)
            self.ctx = self.browser.new_context(viewport={"width": 1366, "height": 768})
            self.page = self.ctx.new_page()
            self.page.add_init_script(STEALTH_INJECTION_V4)
            self._initialized = True
            return True
        except Exception as e:
            self.logger.error(f"Browser Init Error: {e}")
            return False

    def close(self):
        try:
            if self.page: self.page.close()
            if self.ctx: self.ctx.close()
            if self.browser: self.browser.close()
            if self.pw: self.pw.stop()
        except: pass
        self._initialized = False
        self.page = None

    def _safe_click(self, selector, timeout=5000):
        if not validate_selector(selector): return False
        try:
            loc = self.page.locator(selector).first
            loc.wait_for(state="visible", timeout=timeout)
            loc.click()
            return True
        except: return False

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
        login_btn = selectors.get("login_btn", "text=Login")
        if self._safe_click(login_btn):
            return True
        return False

    def navigate_to_match(self, teams, selectors):
        if not self.launch_browser(): return False
        return True # Stub

    # --- LOGICA PIAZZAMENTO AVANZATA ---
    def place_bet(self, teams, market, stake):
        """
        Gestisce sia la modalità DEMO che LIVE in base a self.allow_place
        """
        self.logger.info(f"🏁 Avvio procedura scommessa: {stake}€ su {teams}")

        if not self.allow_place:
            # MODALITÀ DEMO
            self.logger.info(f"🛡️ [DEMO] Simulazione click scommessa su {teams} riuscita.")
            return True

        # MODALITÀ LIVE (SOLDI VERI)
        self.logger.warning(f"💸 [LIVE] Tentativo di piazzamento reale...")
        
        selectors = self._load_selectors()
        input_sel = selectors.get("stake_input", "input.bs-Stake_Input") 
        btn_sel = selectors.get("place_button", ".bs-BtnPlace")

        # 1. Inserimento Stake
        if not self._safe_fill(input_sel, str(stake)):
            self.logger.error("❌ [LIVE] Impossibile inserire lo stake.")
            return False
        
        time.sleep(0.5) 

        # 2. Click Scommetti
        if self._safe_click(btn_sel):
            self.logger.info(f"🚀 [LIVE] SCOMMESSA INVIATA CORRETTAMENTE: {stake}€")
            return True
        else:
            self.logger.error("❌ [LIVE] Click su 'Scommetti' fallito.")
            return False

    def _load_selectors(self):
        import yaml
        try:
            with open(f"config/{self.selector_file}", "r") as f:
                return yaml.safe_load(f)
        except: return {}

    def set_selector_file(self, f): self.selector_file = f
    def check_health(self): return self.page and not self.page.is_closed()
    def recover_session(self): self.close(); self.launch_browser()
    def set_trainer(self, t): pass
    def set_healer(self, h): pass
    def take_screenshot_b64(self): return ""
    def get_dom_snapshot(self): return ""
