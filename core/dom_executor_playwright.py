import time
import threading
import logging
import re
from playwright.sync_api import sync_playwright
from core.human_mouse import HumanMouse
from core.anti_detect import STEALTH_INJECTION_V4

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
                self._initialized = True
                
                try:
                    self.page.goto("https://www.bet365.it", timeout=60000)
                    self.page.wait_for_load_state("domcontentloaded")
                except Exception as e: self.logger.warning(f"Home load warning: {e}")
                return True
            except Exception as e:
                return False

    def ensure_login(self): return True

    def navigate_to_match(self, teams):
        if not self.launch_browser(): return False
        try:
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
        except Exception: return False

    def find_odds(self, teams, market):
        try:
            odds_elements = self.page.locator(".gl-Participant_General > .gl-Participant_Odds")
            if odds_elements.count() > 0:
                return float(odds_elements.first.inner_text().strip())
            return None
        except: return None

    # 🟡 FIX 5 — LETTURA SALDO BOOKMAKER REALE
    def get_balance(self):
        try:
            bal_el = self.page.locator(".hm-Balance").first
            if bal_el.is_visible():
                txt = bal_el.inner_text().replace("€", "").replace(",", ".").strip()
                return float(txt)
            return None
        except: return None

    # 🔴 FIX 1 & 5 — EXECUTOR REALE, BLOCCO SALDO & QUOTA CAMBIATA
    def place_bet(self, teams, market, stake):
        if not self.allow_place:
            self.logger.warning("🛡️ SAFE MODE ATTIVO - bet bloccata, eseguo simulazione logica.")
        
        try:
            self.logger.info(f"💸 Tentativo bet: {teams} | Stake: {stake}€")

            # A. Controllo Saldo Reale
            balance = self.get_balance()
            if balance is not None and balance < stake:
                self.logger.error(f"❌ Saldo insufficiente ({balance}€ < {stake}€)")
                if self.allow_place: raise Exception("Saldo insufficiente sul bookmaker")

            # 1. Clic quota
            odds_btn = self.page.locator(".gl-Participant_Odds").first
            if not odds_btn.is_visible(): raise Exception("Quota non trovata o sospesa")
            odds_btn.click()

            self.page.wait_for_timeout(1200)

            # 2. Verifica popup aperto
            popup = self.page.locator(".bs-BetSlip, .bs-Content")
            if not popup.is_visible(): raise Exception("Popup ticket non aperto")

            # 3. Inserisci stake
            stake_input = self.page.locator("input.bs-Stake_Input, input.st-Stake_Input").first
            stake_input.click()
            stake_input.fill(str(stake))

            self.page.wait_for_timeout(500)

            # 4. Verifica quota disponibile / cambiata live
            body = self.page.inner_text("body").lower()
            if "quota cambiata" in body or "non disponibile" in body or "suspended" in body:
                raise Exception("Quota cambiata live o mercato sospeso")

            # --- BLOCCO SICUREZZA ---
            if not self.allow_place:
                close_btn = self.page.locator(".bs-BetSlipHeader_Close").first
                if close_btn.is_visible(): close_btn.click()
                return True # Test superato

            # 5. Click piazza (SOLDI VERI)
            place_btn = self.page.locator("button.bs-PlaceBetButton, button.st-PlaceBetButton").first
            if not place_btn.is_enabled(): raise Exception("Pulsante piazza disabilitato")
            place_btn.click()

            self.page.wait_for_timeout(2500)
            
            # Verifica ricevuta
            receipt = self.page.locator(".bs-Receipt, .st-Receipt")
            if receipt.is_visible():
                self.page.locator("button.bs-Receipt_Done").first.click()
                return True
            raise Exception("Ricevuta non confermata")

        except Exception as e:
            self.logger.error(f"❌ Bet fallita: {e}")
            return False

    # 🔴 FIX 2 — CONTROLLO BET APERTA (NAVIGAZIONE DOM SPA)
    def check_open_bet(self):
        try:
            self.logger.info("🔍 Controllo scommesse aperte (via DOM)...")
            my_bets_btn = self.page.locator(".hm-MainHeaderCentreWide_MyBets, .hm-MainHeader_MyBets").first
            
            if my_bets_btn.is_visible():
                my_bets_btn.click()
                self.page.wait_for_timeout(1500)

                open_tab = self.page.locator("text='In corso', text='Open'").first
                if open_tab.is_visible(): open_tab.click()
                self.page.wait_for_timeout(1000)

                count = self.page.locator(".myb-BetItem, .myb-BetParticipant").count()

                close_btn = self.page.locator(".myb-MyBetsHeader_CloseButton, .myb-CloseButton").first
                if close_btn.is_visible(): close_btn.click()

                if count > 0:
                    self.logger.warning(f"⚠️ Rilevate {count} scommesse aperte su Bet365")
                    return True
            return False
        except Exception as e:
            self.logger.error(f"❌ Check bet open error: {e}")
            return False

    # 🔴 FIX 3 & 4 — LETTURA ESITO 1° RIGA + PAYOUT REALE
    def check_settled_bets(self):
        try:
            my_bets_btn = self.page.locator(".hm-MainHeaderCentreWide_MyBets, .hm-MainHeader_MyBets").first
            if my_bets_btn.is_visible():
                my_bets_btn.click()
                self.page.wait_for_timeout(1500)

            settled_tab = self.page.locator("text='Risolute', text='Settled'").first
            if settled_tab.is_visible():
                settled_tab.click()
                self.page.wait_for_timeout(1500)

            # Legge SOLO la prima scommessa in lista
            first_bet = self.page.locator(".myb-SettledBetItem, .myb-BetItem").first
            if not first_bet.is_visible():
                close_btn = self.page.locator(".myb-MyBetsHeader_CloseButton, .myb-CloseButton").first
                if close_btn.is_visible(): close_btn.click()
                return None

            txt = first_bet.inner_text().lower()
            status = None
            if "vinta" in txt or "won" in txt: status = "WIN"
            elif "persa" in txt or "lost" in txt: status = "LOSS"
            elif "void" in txt or "annullata" in txt or "rimborsata" in txt: status = "VOID"

            # FIX 4: Estrazione Payout Esatto
            payout = 0.0
            if status == "WIN":
                payout_el = first_bet.locator(".myb-BetItem_Return, .myb-SettledBetItem_Returns, .myb-SettledBetItem_Return").first
                if payout_el.is_visible():
                    pay_txt = payout_el.inner_text().replace("€","").replace(",",".").strip()
                    try:
                        # Cerca il numero dentro il testo (es. "Ritorno: 25.50")
                        payout = float(re.search(r"(\d+\.\d+)", pay_txt).group(1))
                    except: pass

            close_btn = self.page.locator(".myb-MyBetsHeader_CloseButton, .myb-CloseButton").first
            if close_btn.is_visible(): close_btn.click()

            return {"status": status, "payout": payout}
        except Exception as e:
            self.logger.error(f"❌ Check settled error: {e}")
            return None

    def close(self):
        try:
            if self.browser: self.browser.close()
        except: pass