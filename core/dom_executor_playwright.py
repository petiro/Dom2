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
        self.start_time = None # 🟡 FIX 10: Timer Recycle

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
                self.start_time = time.time() # 🟡 Avvio timer
                
                try:
                    self.page.goto("https://www.bet365.it", timeout=60000)
                    self.page.wait_for_load_state("domcontentloaded")
                except Exception as e: self.logger.warning(f"Home load warning: {e}")
                return True
            except Exception as e:
                return False

    # 🟡 FIX 10: RECYCLE BROWSER
    def recycle_browser(self):
        self.logger.warning("🔄 Eseguo Recycle completo del Browser...")
        try:
            if self.browser: self.browser.close()
        except: pass
        self._initialized = False
        self.page = None
        self.browser = None
        return self.launch_browser()

    # 🔴 FIX 8: IS_LOGGED
    def is_logged(self):
        try:
            if self.page.locator("text='Accedi', text='Login'").count() > 0:
                return False
            if self.page.locator(".hm-Balance").count() > 0:
                return True
            return True
        except:
            return False

    def ensure_login(self):
        if not self.launch_browser(): return False
        
        try:
            if self.is_logged() or self.page.locator(".hm-Balance").count() > 0:
                return True

            self.logger.info("🔑 Esecuzione Login su Bet365...")
            config_loader = __import__('core.config_loader').config_loader.ConfigLoader()
            config = config_loader.load_config()
            username = config.get("betting", {}).get("username", "")
            password = config.get("betting", {}).get("password", "")

            if not username or not password:
                self.logger.error("❌ Credenziali mancanti in config.yaml")
                return False

            login_btn = self.page.locator(".hm-MainHeaderRHSLoggedOutWide_Login, text='Login', text='Accedi'").first
            if login_btn.is_visible():
                login_btn.click()
                self.page.wait_for_timeout(1500)

            self.page.locator(".lms-StandardLogin_Username, input[type='text']").first.fill(username)
            self.page.locator(".lms-StandardLogin_Password, input[type='password']").first.fill(password)
            self.page.wait_for_timeout(500)

            self.page.locator(".lms-LoginButton").first.click()
            self.page.wait_for_selector(".hm-Balance", timeout=10000)
            self.logger.info("✅ Login effettuato con successo!")
            return True
        except Exception as e:
            self.logger.error(f"❌ Login Fallito: {e}")
            return False

    def navigate_to_match(self, teams):
        if not self.launch_browser(): return False
        if not self.ensure_login(): return False
        
        try:
            self.logger.info(f"🔍 Cerco la partita: {teams}")
            search_btn = self.page.locator(".hm-MainHeaderCentreWide_SearchIcon, .hm-MainHeader_SearchIcon").first
            if search_btn.is_visible(): search_btn.click()
            self.page.wait_for_timeout(1500)
            
            home_team = teams.split("-")[0].strip() if "-" in teams else teams
            input_box = self.page.locator("input.hm-MainHeaderCentreWide_SearchInput, input.sml-SearchInput").first
            input_box.fill(home_team)
            self.page.wait_for_timeout(3000)

            results = self.page.locator(".sml-SearchParticipant_Name, .sml-EventParticipant")
            if results.count() > 0:
                results.first.click()
                self.page.wait_for_load_state("domcontentloaded")
                self.logger.info(f"🎯 Partita trovata e aperta!")
                return True
            self.logger.error(f"❌ Nessun risultato trovato per: {home_team}")
            return False
        except Exception: return False

    def find_odds(self, teams, market):
        if not self.launch_browser(): return None
        try:
            self.logger.info(f"📊 Cerco la quota per il mercato: {market}")
            self.page.wait_for_timeout(2000)
            odds_elements = self.page.locator(".gl-Participant_General > .gl-Participant_Odds")
            if odds_elements.count() > 0:
                quota_text = odds_elements.first.inner_text().strip()
                quota = float(quota_text.replace(",", "."))
                self.logger.info(f"📈 Quota trovata: {quota}")
                return quota
            self.logger.error("❌ Quota non trovata o mercato sospeso.")
            return None
        except Exception as e:
            self.logger.error(f"❌ Errore lettura quota: {e}")
            return None

    def get_balance(self):
        if not self.launch_browser(): return None
        try:
            bal_el = self.page.locator(".hm-Balance").first
            if bal_el.is_visible():
                txt = bal_el.inner_text().replace("€", "").replace(",", ".").strip()
                return float(txt)
            return None
        except: return None

    # 🔴 FIX 7 & 8: RETRY QUOTA E SESSION GUARD
    def place_bet(self, teams, market, stake):
        if not self.launch_browser(): return False
        
        # 🔴 FIX 8: Controllo login prima della bet
        if not self.is_logged():
            self.logger.error("❌ Sessione scaduta")
            return False

        if not self.allow_place:
            self.logger.warning("🛡️ SAFE MODE ATTIVO - bet bloccata")
        
        try:
            self.logger.info(f"💸 Tentativo bet: {teams} | Stake: {stake}€")

            # Saldo reale
            balance = self.get_balance()
            if balance is not None and balance < stake:
                self.logger.error(f"❌ Saldo insufficiente ({balance} < {stake})")
                if self.allow_place: return False

            odds_btn = self.page.locator(".gl-Participant_Odds").first
            if not odds_btn.is_visible(): raise Exception("Quota non trovata o sospesa")
            odds_btn.click()
            self.page.wait_for_timeout(1200)

            popup = self.page.locator(".bs-BetSlip, .bs-Content")
            if not popup.is_visible(): raise Exception("Popup non aperto")

            stake_input = self.page.locator("input.bs-Stake_Input, input.st-Stake_Input").first
            stake_input.click()
            stake_input.fill(str(stake))
            self.page.wait_for_timeout(500)

            # 🔴 FIX 7: RETRY QUOTA CAMBIATA
            bet_placed = False
            for attempt in range(3):
                body = self.page.inner_text("body").lower()
                if "suspended" in body or "quota cambiata" in body or "non disponibile" in body or "accetta modifiche" in body:
                    self.logger.warning(f"⚠️ Quota sospesa/cambiata (Retry {attempt+1}/3). Retry in 3s...")
                    self.page.wait_for_timeout(3000)
                    continue

                if not self.allow_place:
                    close_btn = self.page.locator(".bs-BetSlipHeader_Close").first
                    if close_btn.is_visible(): close_btn.click()
                    return True # Simulazione OK

                place_btn = self.page.locator("button.bs-PlaceBetButton, button.st-PlaceBetButton").first
                if place_btn.is_enabled():
                    place_btn.click()
                    bet_placed = True
                    break
                else:
                    self.logger.warning("Pulsante disabilitato. Retry in 3s...")
                    self.page.wait_for_timeout(3000)

            if not bet_placed:
                raise Exception("Impossibile piazzare: quota sempre sospesa")

            self.page.wait_for_timeout(2500)
            receipt = self.page.locator(".bs-Receipt, .st-Receipt")
            if receipt.is_visible():
                self.logger.info("✅ BET CONFERMATA")
                self.page.locator("button.bs-Receipt_Done").first.click()
                return True
                
            raise Exception("Ricevuta non confermata")

        except Exception as e:
            self.logger.error(f"❌ Errore bet: {e}")
            return False

    def check_open_bet(self):
        if not self.launch_browser(): return False # 🔴 FIX 4
        try:
            self.logger.info("🔍 Controllo scommesse aperte (via DOM)...")
            # 🔴 FIX 5: NIENTE GOTO, SOLO CLICK DOM
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

    def check_settled_bets(self):
        if not self.launch_browser(): return None # 🔴 FIX 4
        try:
            # 🔴 FIX 5: NIENTE GOTO
            my_bets_btn = self.page.locator(".hm-MainHeaderCentreWide_MyBets, .hm-MainHeader_MyBets").first
            if my_bets_btn.is_visible():
                my_bets_btn.click()
                self.page.wait_for_timeout(1500)

            settled_tab = self.page.locator("text='Risolute', text='Settled'").first
            if settled_tab.is_visible():
                settled_tab.click()
                self.page.wait_for_timeout(1500)

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

            payout = 0.0
            if status == "WIN":
                payout_el = first_bet.locator(".myb-BetItem_Return, .myb-SettledBetItem_Returns, .myb-SettledBetItem_Return").first
                if payout_el.is_visible():
                    pay_txt = payout_el.inner_text().replace("€","").replace(",",".").strip()
                    try: payout = float(re.search(r"(\d+\.\d+)", pay_txt).group(1))
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