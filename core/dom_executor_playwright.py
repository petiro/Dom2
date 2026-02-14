import os
import time
from playwright.sync_api import sync_playwright
from core.ai_selector_validator import validate_selector
from core.anti_detect import STEALTH_INJECTION_V4

class DomExecutorPlaywright:
    def __init__(self, logger, headless=False, allow_place=False, pin=None,
                 chrome_profile="Default", use_real_chrome=True):
        self.logger = logger
        self.headless = headless
        self.allow_place = allow_place 
        self.pw = None
        self.browser = None
        self.page = None
        self._initialized = False
        self.selector_file = "selectors.yaml"

    def set_live_mode(self, enabled: bool):
        self.allow_place = enabled
        mode = "LIVE (SOLDI VERI)" if enabled else "DEMO"
        self.logger.warning(f"🔧 Executor impostato su: {mode}")

    def launch_browser(self):
        if self._initialized: return True
        try:
            self.pw = sync_playwright().start()
            args = ["--disable-blink-features=AutomationControlled", "--start-maximized"]
            self.browser = self.pw.chromium.launch(headless=self.headless, args=args)
            ctx = self.browser.new_context(viewport={"width": 1366, "height": 768})
            self.page = ctx.new_page()
            self.page.add_init_script(STEALTH_INJECTION_V4)
            self._initialized = True
            return True
        except Exception as e:
            self.logger.error(f"Browser Init Error: {e}")
            return False

    def close(self):
        try:
            if self.page: self.page.close()
            if self.browser: self.browser.close()
            if self.pw: self.pw.stop()
        except: pass
        self._initialized = False

    def recycle_browser(self):
        """Richiesto dai test di integrità"""
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

    # --- VERIFICA REALE SCOMMESSA ---
    def verify_placement(self, teams):
        """
        1. Clicca 'Scommesse'
        2. Clicca 'In Corso'
        3. Cerca il team
        """
        self.logger.info("🕵️ VERIFICA: Controllo tab 'In Corso'...")
        sels = self._load_selectors()
        
        # 1. Menu "Scommesse" (header)
        btn_bets = sels.get("my_bets_button", "text=Scommesse")
        if not self._safe_click(btn_bets):
            self.logger.warning("⚠️ Impossibile aprire 'Le mie scommesse'")
            return False
        
        time.sleep(2.0) # Attesa animazione menu

        # 2. Tab "In Corso"
        # Cerchiamo esattamente il testo che hai detto tu
        btn_running = sels.get("filter_running", "text=In Corso")
        self._safe_click(btn_running)
        
        time.sleep(1.5) # Attesa caricamento lista

        # 3. Verifica Presenza
        team_name = teams.split("-")[0].strip() # Es. "Inter"
        try:
            # Cerca testo visibile nella pagina
            if self.page.get_by_text(team_name).count() > 0:
                self.logger.info(f"✅ VERIFICATO: Trovata scommessa attiva per '{team_name}'")
                # Chiude il menu (tasto ESC o click fuori)
                self.page.keyboard.press("Escape")
                return True
            else:
                self.logger.error(f"❌ FALLITO: '{team_name}' NON trovata in tab 'In Corso'")
                self.page.keyboard.press("Escape")
                return False
        except:
            return False

    def place_bet(self, teams, market, stake):
        self.logger.info(f"🏁 Avvio scommessa: {stake}€ su {teams}")
        
        if not self.allow_place:
            self.logger.info("🛡️ [DEMO] Simulazione OK.")
            return True

        # --- LIVE ---
        sels = self._load_selectors()
        
        # 1. Inserisci Stake
        inp = sels.get("stake_input", "input.bs-Stake_Input")
        if not self._safe_fill(inp, str(stake)): return False
        time.sleep(0.5)

        # 2. Clicca Scommetti
        btn = sels.get("place_button", ".bs-BtnPlace")
        if not self._safe_click(btn): return False
        
        self.logger.info("⏳ Attesa elaborazione sito (3s)...")
        time.sleep(3.0)

        # 3. VERIFICA
        return self.verify_placement(teams)
    
    # Stubs
    def ensure_login(self, s): 
        if not self.launch_browser(): return False
        return True # Assumiamo login fatto o gestito altrove
    def navigate_to_match(self, t, s): return True
    def check_health(self): return True
