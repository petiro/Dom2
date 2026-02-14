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
        
        # Variabile per modalità DEMO (False) o LIVE (True)
        self.allow_place = allow_place 
        
        self.pw = None
        self.browser = None
        self.ctx = None 
        self.page = None
        self._initialized = False
        self.selector_file = "selectors.yaml"

    def set_live_mode(self, enabled: bool):
        """Abilita o disabilita il piazzamento reale (Switch UI)."""
        self.allow_place = enabled
        mode = "LIVE (SOLDI VERI)" if enabled else "DEMO (Simulazione)"
        self.logger.warning(f"🔧 Executor impostato su: {mode}")

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
            
            # Injection Anti-Detect
            self.page.add_init_script(STEALTH_INJECTION_V4)
            
            self._initialized = True
            return True
        except Exception as e:
            self.logger.error(f"Browser Init Error: {e}")
            return False

    def close(self):
        """Chiude tutto per liberare risorse."""
        try:
            if self.page: self.page.close()
            if self.ctx: self.ctx.close()
            if self.browser: self.browser.close()
            if self.pw: self.pw.stop()
        except: pass
        self._initialized = False
        self.page = None

    def recycle_browser(self):
        """
        ✅ METODO CRITICO RICHIESTO DA TESTER_V4
        Chiude e riapre il browser per pulire la RAM.
        """
        self.logger.info("♻️ Recycling browser session (Memory Cleanup)...")
        self.close()
        time.sleep(2)
        self.launch_browser()

    def recover_session(self):
        """Alias per recycle_browser (compatibilità)"""
        self.recycle_browser()

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
        # Stub navigazione (qui andrebbe la logica di ricerca match)
        return True

    # --- VERIFICA PARANOICA (POST-CLICK) ---
    def verify_placement(self, teams):
        """
        Va su 'Le mie scommesse' -> 'In Corso' e controlla se il match esiste.
        """
        self.logger.info("🕵️ VERIFICA: Controllo se la scommessa è realmente 'In Corso'...")
        
        selectors = self._load_selectors()
        
        # 1. Clicca su "Scommesse" (Menu utente) o "Le mie scommesse"
        btn_my_bets = selectors.get("my_bets_button", "text=Scommesse") 
        if not self._safe_click(btn_my_bets):
            self.logger.warning("⚠️ Impossibile aprire menu 'Le mie scommesse'")
            return False
            
        time.sleep(1.5)
        
        # 2. Clicca su "In Corso"
        btn_running = selectors.get("filter_running", "text=In Corso")
        self._safe_click(btn_running)
        
        time.sleep(1.0)
        
        # 3. Cerca il nome della squadra
        team_keyword = teams.split("-")[0].strip() 
        
        try:
            if self.page.locator(f"text={team_keyword}").count() > 0:
                self.logger.info(f"✅ CONFERMATO: Trovata scommessa attiva per '{team_keyword}'")
                self.page.keyboard.press("Escape") # Chiude menu
                return True
            else:
                self.logger.error(f"❌ FALLITO: Nessuna traccia di '{team_keyword}' in 'In Corso'")
                self.page.keyboard.press("Escape")
                return False
        except:
            return False

    # --- PIAZZAMENTO INTELLIGENTE ---
    def place_bet(self, teams, market, stake):
        """
        Gestisce DEMO vs LIVE e chiama la verifica se necessario.
        """
        self.logger.info(f"🏁 Avvio procedura scommessa: {stake}€ su {teams}")

        # 1. MODALITÀ DEMO
        if not self.allow_place:
            self.logger.info(f"🛡️ [DEMO] Simulazione click scommessa riuscita.")
            return True 

        # 2. MODALITÀ LIVE
        self.logger.warning(f"💸 [LIVE] Tentativo di piazzamento reale...")
        
        selectors = self._load_selectors()
        input_sel = selectors.get("stake_input", "input.bs-Stake_Input") 
        btn_sel = selectors.get("place_button", ".bs-BtnPlace")

        # Inserimento Stake
        if not self._safe_fill(input_sel, str(stake)):
            self.logger.error("❌ [LIVE] Impossibile inserire lo stake.")
            return False
        
        time.sleep(0.5) 

        # Click Scommetti
        if not self._safe_click(btn_sel):
            self.logger.error("❌ [LIVE] Click su 'Scommetti' fallito.")
            return False
            
        # 3. VERIFICA REALE
        self.logger.info("⏳ Attesa elaborazione sito...")
        time.sleep(3.0) 
        
        if self.verify_placement(teams):
            return True
        else:
            self.logger.critical("🚨 Scommessa NON trovata nello storico!")
            return False

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
    def take_screenshot_b64(self): return ""
    def get_dom_snapshot(self): return ""
