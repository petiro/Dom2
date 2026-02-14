import os
import sys
import time
from playwright.sync_api import sync_playwright
from core.ai_selector_validator import validate_selector
from core.anti_detect import STEALTH_INJECTION_V4

class DomExecutorPlaywright:
    def __init__(self, logger, headless=False, allow_place=False, pin=None,
                 chrome_profile="Default", use_real_chrome=True):
        # SALVIAMO IL LOGGER PASSATO DA MAIN
        self.logger = logger 
        self.headless = headless
        self.allow_place = allow_place 
        self.use_real_chrome = use_real_chrome
        
        self.pw = None
        self.browser = None
        self.page = None
        self._initialized = False
        self.selector_file = "selectors.yaml"
        
        # Test immediato di scrittura
        self.logger.info("✅ EXECUTOR: Inizializzato correttamente.")

    def set_live_mode(self, enabled: bool):
        self.allow_place = enabled
        mode = "LIVE (SOLDI VERI)" if enabled else "DEMO"
        self.logger.warning(f"🔧 Executor impostato su: {mode}")

    def launch_browser(self):
        if self._initialized: return True
        try:
            self.logger.info("🌐 Avvio Browser Playwright...")
            self.pw = sync_playwright().start()
            
            args = [
                "--disable-blink-features=AutomationControlled",
                "--start-maximized",
                "--no-sandbox",
                "--disable-infobars",
                "--disable-extensions",
                "--window-position=0,0"
            ]
            ignore_args = ["--enable-automation"]

            channel = "chrome" if self.use_real_chrome else "chromium"

            self.browser = self.pw.chromium.launch(
                headless=self.headless,
                channel=channel,
                args=args,
                ignore_default_args=ignore_args
            )
            
            ctx = self.browser.new_context(
                viewport={"width": 1920, "height": 1080}, 
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            
            self.page = ctx.new_page()
            self.page.add_init_script(STEALTH_INJECTION_V4)
            
            self._initialized = True
            self.logger.info("✅ Browser avviato con successo.")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Errore avvio browser: {e}")
            return False

    def close(self):
        try:
            if self.page: self.page.close()
            if self.browser: self.browser.close()
            if self.pw: self.pw.stop()
            self.logger.info("Browser chiuso.")
        except: pass
        self._initialized = False

    def recycle_browser(self):
        self.logger.info("♻️ Recycling browser...")
        self.close()
        time.sleep(2)
        self.launch_browser()

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

    def _load_selectors(self):
        import yaml
        try:
            with open(f"config/{self.selector_file}", "r") as f: return yaml.safe_load(f)
        except: return {}

    def verify_placement(self, teams):
        self.logger.info("🕵️ VERIFICA: Controllo tab 'In Corso'...")
        sels = self._load_selectors()
        
        btn_bets = sels.get("my_bets_button", "text=Scommesse")
        if not self._safe_click(btn_bets):
            self.logger.warning("⚠️ Impossibile aprire menu scommesse")
            return False
            
        time.sleep(2.0)
        btn_running = sels.get("filter_running", "text=In Corso")
        self._safe_click(btn_running)
        time.sleep(1.5)
        
        team_name = teams.split("-")[0].strip()
        try:
            if self.page.get_by_text(team_name).count() > 0:
                self.logger.info(f"✅ VERIFICATO: Trovata bet per '{team_name}'")
                self.page.keyboard.press("Escape")
                return True
            else:
                self.logger.error(f"❌ FALLITO: '{team_name}' non trovata.")
                self.page.keyboard.press("Escape")
                return False
        except: return False

    def place_bet(self, teams, market, stake):
        self.logger.info(f"🏁 Avvio scommessa: {stake}€ su {teams}")
        
        if not self.allow_place:
            self.logger.info("🛡️ [DEMO] Simulazione OK.")
            return True

        sels = self._load_selectors()
        inp = sels.get("stake_input", "input.bs-Stake_Input")
        if not self._safe_fill(inp, str(stake)): 
            self.logger.error("❌ Errore input stake")
            return False
        
        time.sleep(0.5)
        btn = sels.get("place_button", ".bs-BtnPlace")
        if not self._safe_click(btn): 
            self.logger.error("❌ Errore click scommetti")
            return False
            
        self.logger.info("⏳ Attesa elaborazione...")
        time.sleep(3.0) 
        
        return self.verify_placement(teams)

    # Stubs
    def ensure_login(self, s): 
        if not self.launch_browser(): return False
        return True
    def navigate_to_match(self, t, s): return True
    def check_health(self): return True
    def set_trainer(self, t): pass
    def set_healer(self, h): pass
    def take_screenshot_b64(self): return ""
    def get_dom_snapshot(self): return ""
