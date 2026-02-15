import os
import time
import random
import base64
import threading
from playwright.sync_api import sync_playwright
from core.ai_selector_validator import validate_selector
from core.anti_detect import STEALTH_INJECTION_V4
from core.human_behavior import HumanInput  # FIX BUG-10: Usa HumanInput

_ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


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
        self.human = None  # FIX BUG-10
        self._internal_lock = threading.Lock()  # Thread safety per operazioni Playwright

    def set_live_mode(self, enabled: bool):
        self.allow_place = enabled
        mode = "LIVE (SOLDI VERI)" if enabled else "DEMO"
        self.logger.warning(f"🔧 Executor impostato su: {mode}")

    # --- BROWSER GUARDIAN ---
    def launch_browser(self):
        if self._initialized and self.page and not self.page.is_closed():
            return True

        self.logger.info("🌐 [GUARDIAN] Inizializzazione Playwright...")
        if not self.pw:
            self.pw = sync_playwright().start()

        try:
            # 1. Tentativo aggancio Chrome CDP (Porta 9222)
            self.browser = self.pw.chromium.connect_over_cdp("http://localhost:9222")
            self.ctx = self.browser.contexts[0]

            if self.ctx.pages:
                self.page = self.ctx.pages[0]
                self.logger.info("✅ [GUARDIAN] Agganciato alla sessione Chrome esistente.")
            else:
                self.page = self.ctx.new_page()
                self.logger.info("✅ [GUARDIAN] Nuova tab aperta su Chrome esistente.")

            self.is_attached = True

        except Exception as e:
            self.logger.info(f"ℹ️ Chrome CDP non disponibile ({e}). Avvio nuovo browser...")
            try:
                args = ["--disable-blink-features=AutomationControlled", "--start-maximized"]
                channel = "chrome" if self.use_real_chrome else "chromium"
                self.browser = self.pw.chromium.launch(
                    headless=self.headless, channel=channel, args=args
                )
                self.ctx = self.browser.new_context(viewport={"width": 1920, "height": 1080})
                self.page = self.ctx.new_page()
                self.is_attached = False
            except Exception as e2:
                self.logger.critical(f"❌ [GUARDIAN] Impossibile avviare browser: {e2}")
                return False

        # Iniezione Anti-Detect
        self.page.add_init_script(STEALTH_INJECTION_V4)
        self.human = HumanInput(self.page, self.logger)  # FIX BUG-10
        self._initialized = True
        return True

    def _reset_connection(self):
        """Resets internal connection state to allow full re-initialization."""
        self._initialized = False
        self.pw = None
        self.browser = None
        self.ctx = None
        self.page = None
        self.human = None

    def close(self):
        """Chiude solo la connessione, MAI il browser dell'utente."""
        try:
            if self.browser:
                self.logger.info("🔌 [GUARDIAN] Disconnessione sicura.")
                self.browser.close()
            if self.pw:
                self.pw.stop()
        except Exception:
            pass
        self._reset_connection()

    def recycle_browser(self):
        """Ignora il recycle se siamo agganciati per evitare crash."""
        if self.is_attached:
            self.logger.info("♻️ [SKIP] Recycle ignorato su sessione persistente.")
            return
        self.close()
        return self.launch_browser()

    # --- FIX BUG-08: Percorso assoluto per selectors ---
    def _load_selectors(self):
        import yaml
        sel_path = os.path.join(_ROOT_DIR, "config", self.selector_file)
        try:
            with open(sel_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except Exception:
            return {}

    # --- FIX BUG-13: Metodi mancanti per AITrainer ---
    def get_dom_snapshot(self):
        """Ritorna l'HTML completo della pagina corrente."""
        if not self.launch_browser():
            return ""
        try:
            return self.page.content()
        except Exception as e:
            self.logger.error(f"Errore snapshot DOM: {e}")
            return ""

    def take_screenshot_b64(self):
        """Cattura screenshot e ritorna come base64."""
        if not self.launch_browser():
            return ""
        try:
            screenshot_bytes = self.page.screenshot(type='jpeg', quality=50)
            return base64.b64encode(screenshot_bytes).decode('utf-8')
        except Exception as e:
            self.logger.error(f"Errore screenshot: {e}")
            return ""

    # --- FIX BUG-03/14: Ricerca Odds ---
    def find_odds(self, match_name, market_name):
        """Cerca la quota reale sulla pagina. Ritorna float o None."""
        if not self.launch_browser():
            return None

        self.logger.info(f"🔎 Cerco quota per {match_name} - {market_name}...")

        sels = self._load_selectors()
        odds_selector = sels.get("odds_value", ".gl-ParticipantOddsOnly_Odds")

        try:
            odds_elements = self.page.locator(odds_selector)
            if odds_elements.count() > 0:
                odds_text = odds_elements.first.inner_text().strip()
                return float(odds_text)
        except Exception as e:
            self.logger.warning(f"⚠️ Impossibile leggere odds: {e}")

        return None

    # --- ANTI-TELEPORT & CLICK ---
    def _human_move_and_click(self, locator, timeout=3000):
        """Usa HumanInput se disponibile, altrimenti fallback semplice. Thread-safe."""
        with self._internal_lock:
            try:
                locator.wait_for(state="visible", timeout=timeout)

                if self.human:
                    return self.human.click_locator(locator)

                # Fallback semplice
                box = locator.bounding_box()
                if box:
                    target_x = box["x"] + box["width"] / 2
                    target_y = box["y"] + box["height"] / 2
                    self.page.mouse.move(target_x, target_y, steps=10)
                    time.sleep(random.uniform(0.1, 0.3))
                    self.page.mouse.click(target_x, target_y)
                    return True
                else:
                    locator.click()
                    return True
            except Exception as e:
                self.logger.warning(f"⚠️ [CLICK FAIL] {e}")
                return False

    def _safe_fill(self, selector, text, timeout=3000):
        if not validate_selector(selector):
            return False
        with self._internal_lock:
            try:
                loc = self.page.locator(selector).first
                loc.wait_for(state="visible", timeout=timeout)
                loc.fill(text)
                return True
            except Exception:
                return False

    def verify_placement(self, teams):
        self.logger.info("🕵️ [VERIFY] Controllo tab 'In Corso'...")
        sels = self._load_selectors()

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
            if self.page.get_by_text(team_name).count() > 0:
                self.logger.info(f"✅ [VERIFY] Scommessa TROVATA: {team_name}")
                self.page.keyboard.press("Escape")
                return True
            else:
                self.logger.error(f"❌ [VERIFY] Scommessa NON trovata: {team_name}")
                self.page.keyboard.press("Escape")
                return False
        except Exception:
            return False

    def verify_bet_success(self, teams, selectors=None):
        """Verifica che la scommessa sia stata accettata (non solo cliccata).

        Controlla 3 segnali:
        1. Messaggio di conferma visibile (es. "Scommessa piazzata")
        2. Assenza di errori visibili (es. "Errore", "Rifiutata")
        3. Fallback: verify_placement nella tab scommesse
        """
        if selectors is None:
            selectors = self._load_selectors()

        # 1. Cerca messaggio di conferma
        confirm_sel = selectors.get("bet_confirm_msg", "text=Scommessa piazzata")
        try:
            confirm_loc = self.page.locator(confirm_sel).first
            if confirm_loc.is_visible(timeout=3000):
                self.logger.info("✅ [VERIFY] Conferma scommessa trovata.")
                return True
        except Exception:
            pass

        # 2. Cerca messaggi di errore noti
        error_keywords = selectors.get("bet_error_keywords",
                                       ["Rifiutata", "Errore", "Non disponibile", "Quota cambiata"])
        for kw in error_keywords:
            try:
                if self.page.get_by_text(kw).first.is_visible(timeout=500):
                    self.logger.error(f"❌ [VERIFY] Scommessa rifiutata: '{kw}' trovato.")
                    return False
            except Exception:
                pass

        # 3. Fallback: controlla nella tab scommesse
        self.logger.info("🔍 [VERIFY] Nessuna conferma diretta, controllo tab scommesse...")
        return self.verify_placement(teams)

    def place_bet(self, teams, market, stake):
        self.logger.info(f"🏁 Avvio scommessa: {stake}€ su {teams}")

        if not self.launch_browser():
            return False

        if not self.allow_place:
            self.logger.info("🛡️ [DEMO] Simulazione OK.")
            return True

        # LIVE MODE
        sels = self._load_selectors()

        # Idle behavior prima di inserire lo stake (sembra umano)
        if self.human:
            self.human.idle_fidget()
            time.sleep(random.uniform(0.3, 0.8))

        # Input Stake (usa HumanInput se disponibile)
        stake_sel = sels.get("stake_input", "input.bs-Stake_Input")
        if self.human:
            if not self.human.type_in_field(stake_sel, str(stake)):
                if not self._safe_fill(stake_sel, str(stake)):
                    self.logger.error("❌ Errore input stake")
                    return False
        else:
            if not self._safe_fill(stake_sel, str(stake)):
                self.logger.error("❌ Errore input stake")
                return False

        # Pausa umana: ricontrollo visivo prima di cliccare
        time.sleep(random.uniform(0.5, 1.2))

        # Scroll casuale leggero (simula utente che verifica)
        if self.human and random.random() > 0.5:
            self.human.scroll_random()
            time.sleep(random.uniform(0.2, 0.5))

        # Click "Scommetti" con movimento umano
        btn_place = self.page.locator(sels.get("place_button", ".bs-BtnPlace")).first
        if not self._human_move_and_click(btn_place):
            self.logger.error("❌ Errore click scommetti")
            return False

        self.logger.info("⏳ Attesa elaborazione...")
        time.sleep(random.uniform(2.5, 4.0))

        # Verifica conferma reale prima di dichiarare successo
        return self.verify_bet_success(teams, sels)

    def ensure_login(self, selectors=None):
        """Verifica login reale: controlla saldo, altrimenti clicca login e attende."""
        if not self.launch_browser():
            return False
        if selectors is None:
            selectors = self._load_selectors()

        balance_sel = selectors.get("balance_selector")
        logged_in_sel = selectors.get("logged_in_indicator")

        # 1. Check se gia loggato (saldo visibile O indicatore loggato)
        for check_sel in [balance_sel, logged_in_sel]:
            if check_sel:
                try:
                    loc = self.page.locator(check_sel).first
                    if loc.is_visible():
                        self.logger.info("Gia loggato (indicatore visibile).")
                        return True
                except Exception:
                    pass

        # 2. Cerca e clicca il bottone login
        login_btn = selectors.get("login_button", "text=Login")
        try:
            login_loc = self.page.locator(login_btn).first
            if not login_loc.is_visible():
                # Nessun bottone login e nessun indicatore = forse gia loggato
                self.logger.info("Nessun bottone login trovato. Potrebbe essere gia loggato.")
                return True
        except Exception:
            self.logger.info("Nessun bottone login trovato. Potrebbe essere gia loggato.")
            return True

        if not self._human_move_and_click(login_loc, timeout=5000):
            self.logger.warning("Login button non cliccabile.")
            return False

        # 3. Attendi conferma login (saldo O indicatore O cambio URL)
        start_url = self.page.url
        deadline = time.time() + 20  # Max 20 secondi per login

        while time.time() < deadline:
            # Check indicatori di login riuscito
            for check_sel in [balance_sel, logged_in_sel]:
                if check_sel:
                    try:
                        if self.page.locator(check_sel).first.is_visible():
                            self.logger.info("Login completato (indicatore visibile).")
                            return True
                    except Exception:
                        pass

            # Check se il bottone login e' sparito (buon segno)
            try:
                if not self.page.locator(login_btn).first.is_visible():
                    self.logger.info("Login completato (bottone login sparito).")
                    return True
            except Exception:
                pass

            # Check cambio URL (redirect post-login)
            if self.page.url != start_url:
                self.logger.info("Login completato (URL cambiato).")
                time.sleep(1)
                return True

            time.sleep(0.5)

        self.logger.warning("Login: timeout - nessuna conferma ricevuta.")
        return False

    def navigate_to_match(self, teams, selectors=None):
        """Cerca il match nella barra di ricerca del sito con retry."""
        if not self.launch_browser():
            return False
        if not teams:
            self.logger.warning("Nessun nome squadra fornito.")
            return False
        if selectors is None:
            selectors = self._load_selectors()

        search_btn = selectors.get("search_button", ".s-SearchButton")
        search_input = selectors.get("search_input", "input.s-SearchInput")

        # Idle behavior prima della ricerca
        if self.human:
            self.human.idle_fidget()

        # Apri la barra di ricerca
        if not self._human_move_and_click(
            self.page.locator(search_btn).first, timeout=5000
        ):
            self.logger.warning("Pulsante ricerca non trovato.")
            return False

        time.sleep(random.uniform(0.3, 0.8))

        # Digita il nome della prima squadra
        team_name = teams.split("-")[0].strip() if "-" in teams else teams.strip()

        if self.human:
            self.human.type_in_field(search_input, team_name)
        else:
            self._safe_fill(search_input, team_name)

        time.sleep(random.uniform(1.5, 3.0))

        # Clicca sul primo risultato che contiene il nome della squadra
        try:
            results = self.page.get_by_text(team_name)
            for i in range(min(results.count(), 5)):
                result_loc = results.nth(i)
                if result_loc.is_visible():
                    self._human_move_and_click(result_loc)
                    time.sleep(random.uniform(1.5, 3.0))
                    self.logger.info(f"Navigato al match: {teams}")
                    return True
        except Exception as e:
            self.logger.warning(f"Navigazione match fallita: {e}")

        # Fallback: premi Enter sulla ricerca
        try:
            self.page.keyboard.press("Enter")
            time.sleep(2)
            self.logger.info(f"Navigazione con Enter per: {teams}")
            return True
        except Exception:
            pass

        return False

    def check_health(self):
        """V6: Controlla se il browser e la pagina sono ancora attivi e rispondono."""
        try:
            if self.page is None or self.page.is_closed():
                return False
            # Verifica che la pagina risponda (non sia stuck)
            self.page.evaluate("() => document.readyState")
            return True
        except Exception:
            return False

    def recover_session(self) -> bool:
        """Attempts to recover the browser session.
        Returns True if recovery succeeds, False otherwise."""
        self.logger.warning("🔄 [RECOVERY] Tentativo ripristino sessione...")
        try:
            self._reset_connection()
            return self.launch_browser()
        except Exception as e:
            self.logger.error(f"Session recovery failed: {e}", exc_info=True)
            return False

    # --- V6: HUMAN INTERACTION DIRETTE ---
    def human_click(self, selector):
        """Simula click umano con delay e hover."""
        if not self.launch_browser():
            return False
        try:
            loc = self.page.locator(selector).first
            loc.wait_for(state="visible", timeout=5000)
            loc.hover()
            time.sleep(random.uniform(0.2, 0.5))
            loc.click()
            time.sleep(random.uniform(0.1, 0.3))
            return True
        except Exception as e:
            self.logger.warning(f"Click fallito su {selector}: {e}")
            return False

    def human_fill(self, selector, text):
        """Simula digitazione umana, utilizzando HumanInput se disponibile."""
        if not self.launch_browser():
            return False
        try:
            # Usa HumanInput se disponibile (ritmi biologici avanzati)
            if hasattr(self, "human") and self.human:
                return self.human.type_in_field(selector, text)
            # Fallback: digitazione diretta lettera per lettera
            loc = self.page.locator(selector).first
            loc.wait_for(state="visible", timeout=5000)
            loc.click()
            for char in text:
                self.page.keyboard.type(char)
                time.sleep(random.uniform(0.05, 0.15))
            return True
        except Exception as e:
            self.logger.warning(f"Fill fallito su {selector}: {e}")
            return False
