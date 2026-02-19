import time
import threading
import logging
from playwright.sync_api import sync_playwright
from core.human_mouse import HumanMouse
from core.anti_detect import STEALTH_INJECTION_V4

class DomExecutorPlaywright:
    def __init__(self, logger=None, headless=False, allow_place=False, **kwargs):
        self.logger = logger or logging.getLogger("Executor")
        self.headless = headless
        self.allow_place = allow_place  # Il flag salvavita

        self.pw = None
        self.browser = None
        self.page = None
        self.mouse = None
        self._internal_lock = threading.RLock()
        self._initialized = False

    def launch_browser(self):
        with self._internal_lock:
            try:
                if self._initialized and self.page and not self.page.is_closed(): return True
                self.logger.info(f"🚀 Launching Browser (Headless={self.headless})...")
                if not self.pw: self.pw = sync_playwright().start()
                self.browser = self.pw.chromium.launch(headless=self.headless, args=["--no-sandbox"])
                context = self.browser.new_context(viewport={"width": 1280, "height": 720})
                self.page = context.new_page()
                self.page.add_init_script(STEALTH_INJECTION_V4)
                self.mouse = HumanMouse(self.page, self.logger)
                self._initialized = True
                
                try:
                    self.page.goto("https://www.bet365.it", timeout=60000)
                    self.page.wait_for_load_state("domcontentloaded")
                except Exception as e: self.logger.warning(f"Home load warning: {e}")
                return True
            except Exception as e:
                self.logger.error(f"Browser launch fail: {e}")
                return False

    def ensure_login(self): return True

    def navigate_to_match(self, teams):
        if not self.launch_browser(): return False
        try:
            self.logger.info(f"🔍 Cerca match: {teams}")
            search_btn = self.page.locator(".hm-MainHeaderCentreWide_SearchIcon, .hm-MainHeader_SearchIcon").first
            if search_btn.is_visible(): search_btn.click()
            time.sleep(1.5)
            
            home_team = teams.split("-")[0].strip() if "-" in teams else teams
            input_box = self.page.locator("input.hm-MainHeaderCentreWide_SearchInput, input.sml-SearchInput").first
            input_box.fill(home_team)
            time.sleep(2.5)

            results = self.page.locator(".sml-SearchParticipant_Name")
            if results.count() > 0:
                results.first.click()
                self.page.wait_for_load_state("domcontentloaded")
                return True
            return False
        except Exception as e:
            self.logger.error(f"Navigate Error: {e}")
            return False

    def find_odds(self, teams, market):
        try:
            odds_elements = self.page.locator(".gl-Participant_General > .gl-Participant_Odds")
            if odds_elements.count() > 0:
                txt = odds_elements.first.inner_text().strip()
                if not txt: return None
                try: return float(txt)
                except: return None
            return None
        except: return None

    def place_bet(self, teams, market, stake):
        if not self.page: return False
        try:
            # 1. Clicca la quota
            odds_btn = self.page.locator(".gl-Participant_Odds").first
            if odds_btn.is_visible(): odds_btn.click()
            else: return False
            
            # 2. Aspetta schedina
            slip = self.page.locator(".bs-BetSlip, .bs-Content")
            slip.wait_for(state="visible", timeout=4000)

            # 3. Inserisci importo
            input_stake = self.page.locator("input.bs-Stake_Input, input.st-Stake_Input").first
            input_stake.click()
            input_stake.fill(str(stake))
            time.sleep(0.5)

            # --- IL CONTROLLO DI SICUREZZA ---
            if not self.allow_place:
                self.logger.warning(f"🛑 SIMULATION: Stake {stake}€ inserito. CLICK REALE BLOCCATO.")
                close_btn = self.page.locator(".bs-BetSlipHeader_Close")
                if close_btn.is_visible(): close_btn.click()
                return True # Ritorna True per simulare la vincita/logica

            # 4. Scommetti (SOLDI VERI)
            place_btn = self.page.locator("button.bs-PlaceBetButton, button.st-PlaceBetButton")
            if place_btn.is_enabled():
                place_btn.click()
                self.logger.info(f"💸 BET INVIATA: {stake}€ on {market}")
            else: return False

            # 5. Conferma
            try:
                receipt = self.page.locator(".bs-Receipt, .st-Receipt")
                receipt.wait_for(state="visible", timeout=8000)
                return True
            except: return False

        except Exception as e:
            self.logger.error(f"Place Bet Error: {e}")
            return False

    def verify_bet_success(self, teams):
        # Nel flow attuale la verifica è integrata nel timeout receipt in place_bet
        return True

    def close(self):
        try:
            if self.browser: self.browser.close()
        except: pass
