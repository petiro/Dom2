import time
import random
from playwright.sync_api import sync_playwright
from core.ai_selector_validator import validate_selector
from core.anti_detect import STEALTH_INJECTION_V4

class DomExecutorPlaywright:
    def __init__(self, logger, headless=False, allow_place=False, pin=None,
                 chrome_profile="Default", use_real_chrome=True):
        self.logger = logger
        self.headless = headless
        self.allow_place = allow_place 
        self.use_real_chrome = use_real_chrome
        
        self.pw = None
        self.browser = None
        self.ctx = None 
        self.page = None
        self._initialized = False
        self.is_attached = False 
        self.selector_file = "selectors.yaml"

    def set_live_mode(self, enabled: bool):
        self.allow_place = enabled
        mode = "LIVE (SOLDI VERI)" if enabled else "DEMO"
        self.logger.warning(f"🔧 Executor impostato su: {mode}")

    # --- BROWSER GUARDIAN ---
    def launch_browser(self):
        """
        Tenta di agganciarsi a Chrome esistente (Safe Mode).
        Se fallisce, NON apre finestre a caso ma avvisa l'utente.
        """
        if self._initialized and self.page and not self.page.is_closed():
            return True
        
        self.logger.info("🌐 [GUARDIAN] Inizializzazione Playwright...")
        if not self.pw:
            self.pw = sync_playwright().start()

        try:
            # 1. TENTATIVO DI AGGANCIO (Porta 9222)
            self.browser = self.pw.chromium.connect_over_cdp("http://localhost:9222")
            self.ctx = self.browser.contexts[0]
            
            # Recupera o crea pagina
            if self.ctx.pages:
                self.page = self.ctx.pages[0]
                self.logger.info("✅ [GUARDIAN] Agganciato alla sessione Chrome esistente.")
            else:
                self.page = self.ctx.new_page()
                self.logger.info("✅ [GUARDIAN] Nuova tab aperta su Chrome esistente.")
            
            self.is_attached = True
            self._initialized = True
            
            # Iniezione Anti-Detect
            self.page.add_init_script(STEALTH_INJECTION_V4)
            return True
            
        except Exception as e:
            self.logger.critical(f"❌ [GUARDIAN] Impossibile connettersi a Chrome (Porta 9222).")
            self.logger.critical("👉 Assicurati di aver avviato Chrome con il collegamento speciale!")
            self.is_attached = False
            return False

    def close(self):
        """Chiude solo la connessione, MAI il browser dell'utente."""
        try:
            if self.browser: 
                self.logger.info("🔌 [GUARDIAN] Disconnessione sicura (Chrome resta aperto).")
                self.browser.close() # In modalità connect, questo disconnette solo il CDP
            if self.pw: 
                self.pw.stop()
        except: pass
        self._initialized = False
        self.pw = None

    def recycle_browser(self):
        """Ignora il recycle se siamo agganciati per evitare crash."""
        if self.is_attached:
            self.logger.info("♻️ [SKIP] Recycle ignorato su sessione persistente.")
            return
        self.close()

    # --- ANTI-TELEPORT & FREEZE BREAKER ---
    def _human_move_and_click(self, locator, timeout=3000):
        """
        Simula movimento umano verso l'elemento prima di cliccare.
        Previene i ban e i click fantasma.
        """
        try:
            # 1. Freeze Breaker: Timeout rigoroso
            locator.wait_for(state="visible", timeout=timeout)
            
            # 2. Calcolo coordinate per Anti-Teleport
            box = locator.bounding_box()
            if box:
                target_x = box["x"] + box["width"] / 2
                target_y = box["y"] + box["height"] / 2
                
                # Muove il mouse virtuale (niente pyautogui, tutto interno)
                self.page.mouse.move(target_x, target_y, steps=10) # 10 steps = movimento fluido
                time.sleep(random.uniform(0.1, 0.3)) # Micro pausa umana
                
                # 3. Click
                self.page.mouse.click(target_x, target_y)
                return True
            else:
                # Fallback se non ha box
                locator.click()
                return True
        except Exception as e:
            # Non crashare tutto, ritorna False e logga
            self.logger.warning(f"⚠️ [CLICK FAIL] Elemento non cliccabile o timeout: {e}")
            return False

    def _safe_fill(self, selector, text, timeout=3000):
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
        self.logger.info("🕵️ [VERIFY] Controllo tab 'In Corso'...")
        sels = self._load_selectors()
        
        # Usa il sistema human click
        btn_bets = self.page.locator(sels.get("my_bets_button", "text=Scommesse")).first
        if not self._human_move_and_click(btn_bets):
            self.logger.warning("⚠️ Impossibile aprire menu scommesse")
            return False
            
        time.sleep(1.5)
        
        btn_running = self.page.locator(sels.get("filter_running", "text=In Corso")).first
        self._human_move_and_click(btn_running)
        time.sleep(1.0)
        
        team_name = teams.split("-")[0].strip()
        try:
            # Quick Check (Freeze Breaker)
            if self.page.get_by_text(team_name).count() > 0:
                self.logger.info(f"✅ [VERIFY] Scommessa TROVATA: {team_name}")
                self.page.keyboard.press("Escape")
                return True
            else:
                self.logger.error(f"❌ [VERIFY] Scommessa NON trovata: {team_name}")
                self.page.keyboard.press("Escape")
                return False
        except: return False

    def place_bet(self, teams, market, stake):
        self.logger.info(f"🏁 Avvio scommessa: {stake}€ su {teams}")
        
        if not self.launch_browser(): # Check vitale
            return False

        if not self.allow_place:
            self.logger.info("🛡️ [DEMO] Simulazione OK.")
            return True

        # LIVE MODE
        sels = self._load_selectors()
        
        # Input Stake
        if not self._safe_fill(sels.get("stake_input", "input.bs-Stake_Input"), str(stake)): 
            self.logger.error("❌ Errore input stake")
            return False
        
        time.sleep(0.5)
        
        # Click "Scommetti" con movimento umano
        btn_place = self.page.locator(sels.get("place_button", ".bs-BtnPlace")).first
        if not self._human_move_and_click(btn_place): 
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
