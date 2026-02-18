import time
import threading
import logging
import random
import re
from playwright.sync_api import sync_playwright
from core.human_mouse import HumanMouse
from core.config_paths import CONFIG_DIR, TIMEOUT_MEDIUM, TIMEOUT_SHORT
from core.dom_self_healing import DOMSelfHealing
from core.anti_detect import STEALTH_INJECTION_V4
import yaml
import os

class DomExecutorPlaywright:
    def __init__(self, logger=None, headless=False, allow_place=False, **kwargs):
        self.logger = logger or logging.getLogger("Executor")
        self.headless = headless
        self.allow_place = allow_place
        
        self.pw = None
        self.browser = None
        self.page = None
        self._internal_lock = threading.RLock() # Reentrant Lock per sicurezza
        self._initialized = False
        
        # Self-Healing Integration
        self.healer = DOMSelfHealing(self)
        self._heal_attempts = 0 # Contatore anti-loop
        
        # Carica selettori iniziali
        self.selectors = self._load_selectors()

    def set_live_mode(self, enabled: bool):
        with self._internal_lock:
            self.allow_place = enabled
        self.logger.warning(f"🔧 Executor MODE: {'LIVE (REAL MONEY)' if enabled else 'DEMO'}")

    def launch_browser(self):
        # Check rapido senza lock se già attivo
        if self._initialized and self.page and not self.page.is_closed(): return True
        
        with self._internal_lock:
            # Doppio check sotto lock
            if self._initialized and self.page and not self.page.is_closed(): return True
            
            self.logger.info("🌐 Avvio Browser V8.4...")
            try:
                if not self.pw: self.pw = sync_playwright().start()
                
                args = [
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-infobars",
                    "--disable-dev-shm-usage",
                    "--start-maximized"
                ]
                
                self.browser = self.pw.chromium.launch(headless=self.headless, args=args)
                
                # Context con viewport realistica
                context = self.browser.new_context(
                    viewport={"width": 1920, "height": 1080},
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                )
                
                self.page = context.new_page()
                self.page.add_init_script(STEALTH_INJECTION_V4)
                
                self.mouse = HumanMouse(self.page, self.logger)
                self._initialized = True
                return True
            except Exception as e:
                self.logger.critical(f"❌ Errore critico Browser Launch: {e}")
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
            self.page = None

    def recycle_browser(self):
        self.logger.info("♻️ Recycling Browser Session...")
        self.close()
        return self.launch_browser()

    def _load_selectors(self):
        try:
            path = os.path.join(CONFIG_DIR, "selectors_auto.yaml")
            if not os.path.exists(path):
                path = os.path.join(CONFIG_DIR, "selectors.yaml")
            
            with open(path, "r") as f:
                return yaml.safe_load(f) or {}
        except: return {}

    # =====================================================
    # SMART INTERACTION (CORE)
    # =====================================================

    def _smart_locate(self, key_or_css):
        """
        Cerca elemento con logica:
        1. Prova selettore noto
        2. Se fallisce -> Self Healing
        3. Riprova -> Se fallisce -> Stop
        """
        # Determina CSS iniziale
        css = key_or_css
        is_key = False
        
        # Se è una chiave nota (es. 'place_button'), carica dal config
        if isinstance(key_or_css, str) and not key_or_css.startswith((".", "#", "//", "text=")):
            self.selectors = self._load_selectors() # Refresh veloce
            css = self.selectors.get(key_or_css)
            is_key = True
            
        if not css: return None

        # Anti-Loop Check
        if self._heal_attempts > 2:
            self.logger.error(f"⛔ Healing Loop Detect su {key_or_css}. Abort.")
            return None

        try:
            loc = self.page.locator(css).first
            if loc.is_visible(timeout=2000):
                self._heal_attempts = 0 # Reset su successo
                return loc
            
            raise Exception("Not visible")
            
        except:
            # Fallimento -> Healing se è una chiave
            if is_key:
                self.logger.warning(f"🩹 Elemento '{key_or_css}' non trovato. Attivo Medico...")
                self._heal_attempts += 1
                new_sel = self.healer.heal(key_or_css)
                if new_sel:
                    return self._smart_locate(key_or_css) # Ricorsione controllata
            
            return None

    def click(self, selector_or_key, timeout=TIMEOUT_MEDIUM):
        with self._internal_lock:
            try:
                if not self.launch_browser(): return False
                
                loc = self._smart_locate(selector_or_key)
                if not loc:
                    self.logger.error(f"Click impossibile su: {selector_or_key}")
                    return False
                
                loc.wait_for(state="visible", timeout=timeout)
                loc.scroll_into_view_if_needed()
                
                if self.mouse: self.mouse.click_locator(loc)
                else: loc.click()
                
                return True
            except Exception as e:
                self.logger.warning(f"Click Error: {e}")
                return False

    def human_fill(self, selector_or_key, text):
        with self._internal_lock:
            try:
                if not self.launch_browser(): return False
                
                loc = self._smart_locate(selector_or_key)
                if not loc: return False
                
                loc.click()
                loc.fill("") # Clear
                
                # Digitazione umana
                for char in str(text):
                    self.page.keyboard.type(char)
                    time.sleep(random.uniform(0.03, 0.11))
                
                return True
            except: return False

    def ensure_login(self):
        # Placeholder logica login smart
        return True

    def navigate_to_match(self, teams):
        """Usa la search box intelligente."""
        if not self.launch_browser(): return False
        
        # 1. Cerca Box Ricerca
        if not self.human_fill("search_box", teams):
            self.logger.error("Barra di ricerca non trovata/agibile")
            return False
            
        self.page.keyboard.press("Enter")
        time.sleep(3) # Attesa caricamento risultati
        
        # 2. Clicca primo risultato (Generico)
        try:
            # Qui si potrebbe usare un selettore più specifico se mappato
            self.page.locator(".match-row, .event-row, .search-result").first.click()
            return True
        except:
            self.logger.warning("Nessun risultato partita cliccabile trovato")
            return False

    def find_odds(self, teams, market):
        """Legge la quota in modo resiliente."""
        if not self.launch_browser(): return 0.0
        
        try:
            loc = self._smart_locate("odds_value")
            if not loc: return 0.0
            
            txt = loc.text_content().strip()
            # Pulisce stringa (es. "1.50 €" -> 1.50)
            clean = re.sub(r'[^\d\.,]', '', txt).replace(",", ".")
            return float(clean)
        except: return 0.0

    def place_bet(self, teams, market, stake):
        """Esegue la piazzata reale."""
        if not self.allow_place:
            self.logger.info(f"DEMO: Simulazione bet {stake}€ su {teams}")
            return True
            
        if not self.human_fill("stake_input", str(stake)):
            return False
            
        if not self.click("place_button"):
            return False
            
        return True

    def verify_bet_success(self, teams=None):
        """Verifica VERO successo scommessa (Anti-False-Positive)."""
        if not self.allow_place: return True
        
        try:
            self.page.wait_for_timeout(3000) # Attesa tecnica post-click
            
            # Leggi solo testo visibile body (veloce)
            content = self.page.inner_text("body").lower()[:10000]
            
            # 1. Check Errori Espliciti (Fail Fast)
            error_keywords = ["non accettata", "rifiutata", "errore", "sospesa", "chiusa", "fondi insufficienti"]
            if any(k in content for k in error_keywords):
                self.logger.error("⛔ Scommessa RIFIUTATA dal bookmaker.")
                return False
                
            # 2. Check Successo (Strong Match)
            success_keywords = ["scommessa accettata", "bet placed", "codice aams", "ricevuta", "successo", "confermata"]
            if any(k in content for k in success_keywords):
                self.logger.info("✅ Scommessa CONFERMATA dal sito.")
                return True
                
            self.logger.warning("⚠️ Stato scommessa ambiguo (nessuna conferma/errore chiaro).")
            return False
            
        except Exception as e:
            self.logger.error(f"Verify error: {e}")
            return False