import time
import threading
import logging
import re
import os
import json
import random
from typing import Any
from playwright.sync_api import sync_playwright
from core.human_mouse import HumanMouse
from core.anti_detect import STEALTH_INJECTION_V4

class DomExecutorPlaywright:
    def __init__(self, logger=None, headless=False, allow_place=False, **kwargs):
        self.logger = logger or logging.getLogger("Executor")
        self.headless = headless
        self.allow_place = allow_place

        self.pw: Any = None
        self.browser: Any = None
        self.page: Any = None
        self.mouse: Any = None
        
        self._internal_lock = threading.RLock()
        self.start_time = None 
        
        self.bet_count = 0
        self.login_fails = 0

    def launch_browser(self):
        with self._internal_lock:
            try:
                if self.page and not self.page.is_closed():
                    return True
                    
                self.logger.info(f"🚀 Launching Browser (Headless={self.headless})...")
                if not self.pw: self.pw = sync_playwright().start()
                self.browser = self.pw.chromium.launch(headless=self.headless, args=["--no-sandbox"])
                context = self.browser.new_context(viewport={"width": 1280, "height": 720})
                self.page = context.new_page()
                self.page.add_init_script(STEALTH_INJECTION_V4)
                
                try:
                    self.mouse = HumanMouse(self.page, self.logger)
                except Exception as exc:
                    self.logger.debug(f"Non-critical exception in mouse init: {exc}")
                    self.mouse = None

                self.start_time = time.time()
                
                try:
                    self.page.goto("https://www.bet365.it", timeout=60000)
                    self.page.wait_for_load_state("domcontentloaded")
                except Exception as exc:
                    self.logger.warning(f"Home load warning: {exc}")
                return True
            except Exception as exc:
                self.logger.debug(f"Non-critical exception launch_browser: {exc}")
                return False

    def _stealth_click(self, locator: Any):
        if not self.mouse:
            raise RuntimeError("HumanMouse non inizializzato")
        self.mouse.click(locator)

    def save_blackbox(self, tx_id, error_msg="", data=None, stake=0, quota=0, saldo_db=0, saldo_book=0):
        try:
            os.makedirs("logs", exist_ok=True)
            tx = tx_id or f"CRASH_{int(time.time())}"
            html = "Page closed/None"
            url = "N/A"
            try:
                if self.page and not self.page.is_closed():
                    self.page.screenshot(path=f"logs/blackbox_{tx}.png", full_page=True)
                    html = self.page.content()
                    url = self.page.url
            except Exception as exc:
                self.logger.debug(f"Non-critical exception blackbox screenshot: {exc}")
                
            dump = {
                "tx_id": tx, "error": str(error_msg), "payload": data or {},
                "stake": stake, "quota": quota, "saldo_db": saldo_db, "saldo_book": saldo_book,
                "url": url, "html_snippet": html[:3000] 
            }
            with open(f"logs/blackbox_{tx}.json", "w") as f:
                json.dump(dump, f, indent=4)
            self.logger.critical(f"📦 BLACKBOX COMPLETA SALVATA: logs/blackbox_{tx}.json")
        except Exception as exc:
            self.logger.debug(f"Non-critical exception save_blackbox: {exc}")

    def recycle_browser(self):
        self.logger.warning("🔄 Eseguo Recycle completo del Browser...")
        try:
            if self.page and self.page.context:
                self.page.context.close()
            if self.browser: 
                self.browser.close()
            if self.pw: 
                self.pw.stop()
        except Exception as exc:
            self.logger.debug(f"Non-critical exception recycle: {exc}")
        
        self.page = None
        self.browser = None
        self.pw = None
        self.bet_count = 0
        self.login_fails = 0
        return self.launch_browser()

    def is_logged(self):
        try:
            if self.page.locator("text='Accedi', text='Login'").count() > 0: return False
            if self.page.locator(".hm-Balance").count() > 0: return True
            return True
        except Exception: 
            return False

    # 🔴 FIX DEFINITIVO 11/10: LOGIN DAL VAULT CRIPTATO
    def ensure_login(self, account_id="bet365_main"):
        if not self.launch_browser(): return False
        try:
            if self.is_logged() or self.page.locator(".hm-Balance").count() > 0: 
                self.login_fails = 0
                return True
                
            self.logger.info(f"🔑 Esecuzione Login per account: {account_id}...")
            
            # Lettura e Decriptazione AES al volo
            from core.secure_storage import BookmakerManager
            username, password = BookmakerManager().get_decrypted(account_id)
            
            if not username or not password:
                self.logger.error(f"❌ Account {account_id} non trovato nel Vault o password illeggibile.")
                return False

            login_btn = self.page.locator(".hm-MainHeaderRHSLoggedOutWide_Login, text='Login', text='Accedi'").first
            if login_btn.is_visible():
                self._stealth_click(login_btn)
                self.page.wait_for_timeout(1500)

            self.page.locator(".lms-StandardLogin_Username, input[type='text']").first.fill(username)
            self.page.locator(".lms-StandardLogin_Password, input[type='password']").first.fill(password)
            self.page.wait_for_timeout(500)

            btn_submit = self.page.locator(".lms-LoginButton").first
            self._stealth_click(btn_submit)
            self.page.wait_for_selector(".hm-Balance", timeout=10000)
            
            self.login_fails = 0
            self.logger.info(f"✅ Login su account {account_id} effettuato con successo!")
            return True
        except Exception as exc:
            self.logger.debug(f"Non-critical exception ensure_login: {exc}")
            self.login_fails += 1
            return False

    def navigate_to_match(self, teams):
        if not self.launch_browser(): return False
        if not self.ensure_login(): return False
        try:
            self.logger.info(f"🔍 Cerco la partita: {teams}")
            search_btn = self.page.locator(".hm-MainHeaderCentreWide_SearchIcon, .hm-MainHeader_SearchIcon").first
            if search_btn.is_visible(): self._stealth_click(search_btn)
            self.page.wait_for_timeout(1500)
            
            home_team = teams.split("-")[0].strip() if "-" in teams else teams
            input_box = self.page.locator("input.hm-MainHeaderCentreWide_SearchInput, input.sml-SearchInput").first
            input_box.fill(home_team)
            self.page.wait_for_timeout(3000)

            results = self.page.locator(".sml-SearchParticipant_Name, .sml-EventParticipant")
            if results.count() > 0:
                self._stealth_click(results.first)
                self.page.wait_for_load_state("domcontentloaded")
                return True
            return False
        except Exception as exc:
            self.logger.debug(f"Non-critical exception nav match: {exc}")
            return False

    def find_odds(self, teams, market):
        if not self.launch_browser(): return None
        try:
            self.page.wait_for_timeout(2000) 
            odds_elements = self.page.locator(".gl-Participant_General > .gl-Participant_Odds")
            if odds_elements.count() > 0:
                quota_text = odds_elements.first.inner_text().strip()
                return float(quota_text.replace(",", "."))
            return None
        except Exception as exc:
            self.logger.debug(f"Non-critical exception find odds: {exc}")
            return None

    def get_balance(self):
        if not self.launch_browser(): return None
        try:
            bal_el = self.page.locator(".hm-Balance").first
            if bal_el.is_visible():
                txt = bal_el.inner_text()
                txt = txt.replace("€","").replace("$","").strip()
                txt = txt.replace(".", "").replace(",", ".")
                try: return float(txt)
                except Exception:
                    self.logger.error(f"Parsing saldo fallito: {txt}")
                    return None
            return None
        except Exception as exc:
            self.logger.debug(f"Non-critical exception get balance: {exc}")
            return None

    def place_bet(self, teams, market, stake):
        if not self.launch_browser(): return False
        if not self.is_logged(): return False

        try:
            saldo_pre = self.get_balance()
            if saldo_pre is None:
                self.logger.error("❌ Saldo bookmaker NON leggibile → abort bet sicurezza")
                return False
            if saldo_pre < stake:
                self.logger.error(f"❌ Saldo insufficiente: {saldo_pre} < {stake}")
                return False

            try:
                if self.check_open_bet():
                    self.logger.warning("⚠ Bet già aperta → abort nuova bet sicurezza")
                    return False
            except Exception: pass

            odds_btn = self.page.locator(".gl-Participant_Odds").first
            if not odds_btn.is_visible(): raise Exception("Quota non trovata")
            self._stealth_click(odds_btn)
            self.page.wait_for_timeout(1200)

            popup = self.page.locator(".bs-BetSlip, .bs-Content")
            if not popup.is_visible(): raise Exception("Popup ticket non aperto")

            stake_input = self.page.locator("input.bs-Stake_Input, input.st-Stake_Input").first
            self._stealth_click(stake_input)
            stake_input.fill(str(stake))
            self.page.wait_for_timeout(500)

            bet_placed = False
            for attempt in range(3):
                body = self.page.inner_text("body").lower()
                if "suspended" in body or "quota cambiata" in body or "non disponibile" in body or "accetta modifiche" in body:
                    close_btn = self.page.locator(".bs-BetSlipHeader_Close").first
                    if close_btn.is_visible(): self._stealth_click(close_btn)
                    self.page.wait_for_timeout(2000)
                    if odds_btn.is_visible():
                        self._stealth_click(odds_btn)
                        self.page.wait_for_timeout(1000)
                        if stake_input.is_visible(): stake_input.fill(str(stake))
                    continue

                if not self.allow_place:
                    close_btn = self.page.locator(".bs-BetSlipHeader_Close").first
                    if close_btn.is_visible(): self._stealth_click(close_btn)
                    bet_placed = True
                    break

                place_btn = self.page.locator("button.bs-PlaceBetButton, button.st-PlaceBetButton").first
                if place_btn.is_enabled():
                    self._stealth_click(place_btn)
                    bet_placed = True
                    break
                else: self.page.wait_for_timeout(2000)

            if not bet_placed: raise Exception("Quota permanentemente sospesa.")

            self.page.wait_for_timeout(3000)
            receipt = self.page.locator(".bs-Receipt, .st-Receipt")
            
            if receipt.is_visible() or not self.allow_place:
                self.logger.info("✅ RICEVUTA CONFERMATA A SCHERMO!")
                
                if self.allow_place:
                    time.sleep(random.uniform(1.2, 2.2))
                    saldo_post = self.get_balance()
                    
                    if saldo_post is None:
                        self.logger.error("❌ Saldo post-bet non leggibile → bet incerta")
                        return False
                    if saldo_post >= saldo_pre:
                        self.logger.error("❌ Saldo non cambiato dopo bet → fallita")
                        return False
                        
                    try:
                        open_bet = self.check_open_bet()
                        if open_bet: self.logger.info("Schedina confermata aperta")
                    except Exception: pass
                        
                    self.logger.info(f"✅ Bet confermata finanziariamente. Saldo: {saldo_pre} → {saldo_post}")

                done_btn = self.page.locator("button.bs-Receipt_Done").first
                if done_btn.is_visible(): self._stealth_click(done_btn)

                try:
                    import psutil
                    process = psutil.Process(os.getpid())
                    ram = process.memory_info().rss / 1024 / 1024
                    if ram > 1200:
                        self.logger.critical(f"🚨 RAM alta {ram:.0f}MB → recycle browser preventivo")
                        self.recycle_browser()
                except Exception: pass

                return True
            raise Exception("Ricevuta non confermata")
        except Exception as e:
            self.logger.error(f"❌ Bet fallita: {e}")
            return False

    def check_open_bet(self):
        if not self.launch_browser(): return False
        try:
            my_bets_btn = self.page.locator(".hm-MainHeaderCentreWide_MyBets, .hm-MainHeader_MyBets").first
            if my_bets_btn.is_visible():
                self._stealth_click(my_bets_btn)
                self.page.wait_for_timeout(1500)
                open_tab = self.page.locator("text='In corso', text='Open'").first
                if open_tab.is_visible(): self._stealth_click(open_tab)
                self.page.wait_for_timeout(1000)
                
                count = self.page.locator(".myb-BetItem, .myb-BetParticipant").count()
                try:
                    close = self.page.locator(".myb-CloseButton, .myb-MyBetsHeader_CloseButton").first
                    if close.is_visible(): self._stealth_click(close)
                except Exception: pass

                if count > 0: return True
            return False
        except Exception: return False

    def check_settled_bets(self):
        if not self.launch_browser(): return None
        try:
            my_bets_btn = self.page.locator(".hm-MainHeaderCentreWide_MyBets, .hm-MainHeader_MyBets").first
            if my_bets_btn.is_visible():
                self._stealth_click(my_bets_btn)
                self.page.wait_for_timeout(1500)
            settled_tab = self.page.locator("text='Risolute', text='Settled'").first
            if settled_tab.is_visible():
                self._stealth_click(settled_tab)
                self.page.wait_for_timeout(1500)
            first_bet = self.page.locator(".myb-SettledBetItem, .myb-BetItem").first
            if not first_bet.is_visible():
                try:
                    close = self.page.locator(".myb-CloseButton, .myb-MyBetsHeader_CloseButton").first
                    if close.is_visible(): self._stealth_click(close)
                except Exception: pass
                return None
                
            txt = first_bet.inner_text().lower()
            status = None
            if "vinta" in txt or "won" in txt: status = "WIN"
            elif "persa" in txt or "lost" in txt: status = "LOSS"
            elif "void" in txt or "annullata" in txt or "rimborsata" in txt: status = "VOID"

            payout = 0.0
            if status == "WIN":
                payout_el = first_bet.locator(".myb-BetItem_Return, .myb-SettledBetItem_Returns").first
                if payout_el.is_visible():
                    pay_txt = payout_el.inner_text().replace("€","").replace("$","").strip().replace(".", "").replace(",", ".")
                    match = re.search(r"(\d+\.\d+)", pay_txt)
                    if match:
                        try: payout = float(match.group(1))
                        except Exception: payout = 0.0
                    
            try:
                close = self.page.locator(".myb-CloseButton, .myb-MyBetsHeader_CloseButton").first
                if close.is_visible(): self._stealth_click(close)
            except Exception: pass
            
            return {"status": status, "payout": payout}
        except Exception: return None

    def close(self):
        try:
            if self.page and self.page.context: self.page.context.close()
            if self.browser: self.browser.close()
            if self.pw: self.pw.stop()
        except Exception: pass