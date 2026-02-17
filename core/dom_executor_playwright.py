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
        self.logger.warning(f"🔧 Executor impostato su: {'LIVE (SOLDI VERI)' if enabled else 'DEMO'}")

    def launch_browser(self):
        if self._initialized and self.page and not self.page.is_closed(): return True
        self.logger.info("🌐 Inizializzazione Playwright...")
        try:
            if not self.pw: self.pw = sync_playwright().start()
            
            # Tentativo connessione CDP (Chrome esistente)
            try:
                self.browser = self.pw.chromium.connect_over_cdp("http://localhost:9222")
                self.ctx = self.browser.contexts[0]
                self.page = self.ctx.pages[0] if self.ctx.pages else self.ctx.new_page()
                self.logger.info("✅ Agganciato a Chrome esistente (CDP).")
            except Exception:
                # Fallback: Nuova istanza
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
        """Chiude il browser e ferma Playwright per evitare leak."""
        try:
            if self.browser: self.browser.close()
            if self.pw: self.pw.stop()
        except: pass
        finally:
            self._initialized = False
            self.pw = None
            self.browser = None

    def recycle_browser(self):
        """Riavvia il browser per pulire la sessione (Cookie/Cache/Memoria)."""
        self.logger.info("♻️ Recycling browser session...")
        self.close()
        return self.launch_browser()

    def _load_selectors(self):
        import os
        try:
            with open(os.path.join(CONFIG_DIR, self.selector_file), "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except: return {}

    def click(self, selector_or_locator, timeout=TIMEOUT_MEDIUM):
        """Esegue un click umano su un selettore o locator."""
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
            except Exception as e:
                self.logger.warning(f"Click fallito: {e}")
                return False

    def human_fill(self, selector, text):
        """Simula la digitazione umana."""
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
        """Verifica se l'utente è loggato, altrimenti prova a fare login."""
        if selectors is None: selectors = self._load_selectors()
        if not self.launch_browser(): return False
        
        bal = selectors.get("balance_element")
        if bal:
            try: 
                if self.page.locator(bal).first.is_visible(timeout=TIMEOUT_SHORT): return True
            except: pass
            
        btn = selectors.get("login_button")
        if btn:
            self.logger.info("Tentativo click login...")
            self.click(btn)
            # Attende un po' per eventuale login manuale o caricamento
            time.sleep(2)
            return True
        return False

    def verify_bet_success(self, teams=None, selectors=None):
        """Verifica se la scommessa è stata accettata."""
        if not self.allow_place: return True
        if selectors is None: selectors = self._load_selectors()
        
        try:
            # Metodo 1: Selettore specifico
            msg = selectors.get("success_message", "Scommessa accettata")
            self.page.wait_for_selector(f"text={msg}", timeout=TIMEOUT_LONG)
            return True
        except:
            # Metodo 2: Fallback Regex sul contenuto
            try:
                content = self.page.content().lower()
                if re.search(r"(accettat|success|bet placed|piazzat|codice)", content): return True
            except: pass
            return False

    def navigate_to_match(self, teams, selectors=None):
        """Cerca la partita usando la barra di ricerca."""
        if not teams: return False
        if selectors is None: selectors = self._load_selectors()
        
        box = selectors.get("search_box")
        if not self.human_fill(box, teams): return False
        
        self.page.keyboard.press("Enter")
        time.sleep(2) # Attesa caricamento risultati
        
        res = selectors.get("match_result", ".match-row")
        try:
            self.page.wait_for_selector(res, timeout=TIMEOUT_MEDIUM)
            return self.click(res)
        except: return False

    def place_bet(self, teams, market, stake):
        """Inserisce l'importo e piazza la scommessa."""
        if not self.allow_place: 
            self.logger.info(f"DEMO MODE: Simulazione puntata {stake} su {market}")
            return True
            
        sels = self._load_selectors()
        if not self.human_fill(sels.get("stake_input"), str(stake)): return False
        
        if self.mouse: self.mouse.idle_behavior()
        
        btn = sels.get("place_button")
        if self.click(btn):
            self.logger.info("Pulsante scommetti cliccato.")
            return True
        return False

    def find_odds(self, match, market):
        """
        Cerca la quota reale nella pagina corrente, gestendo anche iframe.
        """
        if not self.launch_browser(): return 0.0
        selectors = self._load_selectors()
        odds_sel = selectors.get("odds_value")
        
        if not odds_sel:
            self.logger.error("❌ Manca 'odds_value' in selectors.yaml")
            return 0.0

        try:
            # Tenta prima nel main frame
            loc = self.page.locator(odds_sel).first
            
            # Se non visibile subito, cerca negli iframe (bookmaker complessi)
            if not loc.is_visible(timeout=1000):
                for frame in self.page.frames:
                    try:
                        frame_loc = frame.locator(odds_sel).first
                        if frame_loc.is_visible(timeout=500):
                            loc = frame_loc
                            self.logger.info(f"✅ Quota trovata in iframe: {frame.name or 'anonimo'}")
                            break
                    except: continue

            # Attesa finale e lettura
            loc.wait_for(state="visible", timeout=3000)
            text = loc.text_content().strip()
            
            # Pulizia avanzata (rimuove spazi, simboli valuta, converte virgola)
            text = text.replace(",", ".").replace("€", "").replace("$", "").strip()
            
            # Verifica che sia un numero valido
            odds = float(text)
            
            # Controllo logico: una quota < 1.01 è probabilmente un errore di parsing o non valida
            if odds < 1.01:
                self.logger.warning(f"⚠️ Quota letta anomala ({odds}), forzo a 0.0")
                return 0.0
                
            self.logger.info(f"📊 Quota confermata dal sito: {odds}")
            return odds
            
        except Exception as e:
            self.logger.warning(f"⚠️ Impossibile leggere quota: {e}")
            return 0.0

    def scan_page_elements(self, url):
        """
        Scansiona la pagina per trovare potenziali selettori (utile per Auto-Mapping).
        """
        if not self.launch_browser(): return []
        
        found_elements = []
        try:
            # Cerca input, bottoni e span con classi significative
            elements = self.page.locator("button, input[type='text'], .price, .odds").all()
            for el in elements[:30]: # Limitiamo a 30 per velocità
                try:
                    txt = el.text_content().strip()[:30]
                    cls = el.get_attribute("class") or ""
                    tag = el.evaluate("el => el.tagName").lower()
                    if txt or cls:
                        found_elements.append(f"Tag: {tag} | Text: {txt} | Class: {cls}")
                except: pass
        except Exception as e:
            self.logger.error(f"Scan error: {e}")
            
        return found_elements