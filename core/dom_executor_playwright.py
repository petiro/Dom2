import time
import threading
import logging
import re
from playwright.sync_api import sync_playwright
from core.human_mouse import HumanMouse
from core.config_paths import TIMEOUT_MEDIUM
from core.anti_detect import STEALTH_INJECTION_V4
import os
import yaml
from core.config_paths import CONFIG_DIR

# Import necessario per il Self-Healing (gestito per evitare loop circolari)
import core.dom_self_healing 

class DomExecutorPlaywright:
    def __init__(self, logger=None, headless=False, allow_place=False, **kwargs):
        self.logger = logger or logging.getLogger("Executor")
        self.headless = headless
        self.allow_place = allow_place  # TRUE = SOLDI VERI, FALSE = SIMULAZIONE

        self.pw = None
        self.browser = None
        self.page = None
        self.mouse = None

        self._internal_lock = threading.RLock()
        self._initialized = False

        self.healer = core.dom_self_healing.DOMSelfHealing(self)
        self._heal_attempts = 0

    def launch_browser(self):
        with self._internal_lock:
            try:
                if self._initialized and self.page and not self.page.is_closed():
                    return True

                self.logger.info(f"🚀 Launching Browser (Headless={self.headless})...")
                if not self.pw:
                    self.pw = sync_playwright().start()

                self.browser = self.pw.chromium.launch(
                    headless=self.headless,
                    args=[
                        "--disable-blink-features=AutomationControlled",
                        "--no-sandbox",
                        "--disable-infobars"
                    ]
                )

                # Creazione contesto con user-agent realistico
                context = self.browser.new_context(
                    viewport={"width": 1280, "height": 720},
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                )
                
                self.page = context.new_page()
                self.page.add_init_script(STEALTH_INJECTION_V4)

                self.mouse = HumanMouse(self.page, self.logger)
                self._initialized = True
                
                # Vai alla home di Bet365 (o sito target)
                try:
                    self.page.goto("https://www.bet365.it", timeout=60000)
                    self.page.wait_for_load_state("domcontentloaded")
                    self._handle_cookie_banner() # Gestione automatica cookies
                except Exception as e:
                    self.logger.warning(f"Home load warning: {e}")

                return True

            except Exception as e:
                self.logger.error(f"Browser launch fail: {e}")
                return False

    def _handle_cookie_banner(self):
        """Tenta di chiudere i cookie banner comuni"""
        try:
            # Esempi di selettori comuni per cookie
            cookie_btns = [
                "button:has-text('Accetta')", 
                "button:has-text('Accept')", 
                ".cc-btn.cc-accept-all"
            ]
            for sel in cookie_btns:
                if self.page.locator(sel).first.is_visible():
                    self.page.locator(sel).first.click()
                    time.sleep(1)
                    break
        except: pass

    def _health_check(self):
        try:
            if not self.page: return False
            self.page.title()
            return True
        except: return False

    def ensure_login(self):
        """
        Verifica login. Se sloggato, logga un warning (login automatico complesso senza credenziali).
        Per ora assume sessione mantenuta o login manuale all'avvio.
        """
        # TODO: Implementare login automatico se hai username/pass in config
        return True

    # ------------------------------------------------------------------
    # 1. NAVIGAZIONE REALE
    # ------------------------------------------------------------------
    def navigate_to_match(self, teams):
        if not self.launch_browser(): return False
        
        try:
            self.logger.info(f"🔍 Searching match: {teams}")
            
            # Clicca lente d'ingrandimento (Search)
            search_btn = self.page.locator(".hm-MainHeaderCentreWide_SearchIcon, .hm-MainHeader_SearchIcon").first
            if search_btn.is_visible():
                search_btn.click()
            else:
                self.logger.warning("Search button not found")
                return False
            
            time.sleep(1.5)

            # Scrive nome squadra (solo la prima per semplicità)
            home_team = teams.split("-")[0].strip() if "-" in teams else teams
            
            input_box = self.page.locator("input.hm-MainHeaderCentreWide_SearchInput, input.sml-SearchInput").first
            input_box.fill(home_team)
            time.sleep(2.5) # Attesa risultati dinamici

            # Clicca Primo Risultato
            results = self.page.locator(".sml-SearchParticipant_Name")
            if results.count() > 0:
                results.first.click()
                self.page.wait_for_load_state("domcontentloaded")
                self.logger.info("✅ Match found & clicked")
                return True
            else:
                self.logger.warning(f"❌ Match '{home_team}' not found in search")
                return False

        except Exception as e:
            self.logger.error(f"Navigate Error: {e}")
            return False

    # ------------------------------------------------------------------
    # 2. LETTURA QUOTE REALE
    # ------------------------------------------------------------------
    def find_odds(self, teams, market):
        """
        Cerca la quota per il mercato specificato.
        Ritorna float (es. 1.50) o None se non trovata/sospesa.
        """
        try:
            # Nota: I selettori qui devono essere precisi per il mercato richiesto.
            # Esempio generico per trovare una quota "cliccabile"
            
            # Strategia semplificata: Cerca prima quota visibile nel contenitore principale
            # In produzione vera, dovresti mappare 'market' -> 'selettore specifico'
            
            odds_elements = self.page.locator(".gl-Participant_General > .gl-Participant_Odds")
            
            if odds_elements.count() > 0:
                txt = odds_elements.first.inner_text().strip()
                if not txt: return None
                
                # Converte frazione in decimale se necessario, o legge decimale
                try:
                    if "/" in txt:
                        num, den = map(int, txt.split("/"))
                        return 1 + (num / den)
                    return float(txt)
                except:
                    return None
            
            return None # Nessuna quota trovata

        except Exception as e:
            self.logger.error(f"Find Odds Error: {e}")
            return None

    # ------------------------------------------------------------------
    # 3. PIAZZAMENTO SCOMMESSA REALE
    # ------------------------------------------------------------------
    def place_bet(self, teams, market, stake):
        if not self.page: return False

        try:
            self.logger.info(f"⚡ Attempting to place bet on {market} | Stake: {stake}")

            # 1. CLICCA QUOTA (Simuliamo click sul primo mercato trovato)
            # In produzione: self._find_specific_market_button(market).click()
            odds_btn = self.page.locator(".gl-Participant_Odds").first
            
            if odds_btn.is_visible():
                odds_btn.click()
            else:
                self.logger.error("❌ Odds button not found (Market suspended?)")
                return False
            
            # 2. ASPETTA SCHEDINA (Bet Slip)
            slip = self.page.locator(".bs-BetSlip, .bs-Content")
            try:
                slip.wait_for(state="visible", timeout=4000)
            except:
                self.logger.error("❌ Bet Slip did not open")
                return False

            # 3. INSERISCI STAKE
            # Bet365 spesso ha un iframe o input diretto.
            input_stake = self.page.locator("input.bs-Stake_Input, input.st-Stake_Input").first
            input_stake.click()
            input_stake.fill(str(stake))
            time.sleep(0.5)

            # 4. SAFETY CHECK (HEDGE MODE)
            if not self.allow_place:
                self.logger.warning(f"🛑 SIMULATION MODE: Stake {stake} inserted but NOT confirmed.")
                # Chiude la schedina per pulizia e non lasciare sporco
                close_btn = self.page.locator(".bs-BetSlipHeader_Close")
                if close_btn.is_visible(): close_btn.click()
                
                return True # Ritorniamo True per dire "Test logica OK"

            # 5. CLICK SCOMMETTI (SOLO QUI SPENDE SOLDI)
            place_btn = self.page.locator("button.bs-PlaceBetButton, button.st-PlaceBetButton")
            
            if place_btn.is_enabled():
                place_btn.click()
                self.logger.info(f"💸 BET SENT: {stake}EUR on {market}")
            else:
                self.logger.warning("⚠️ Place button disabled (Stake too low or Odds changed?)")
                return False

            # 6. VERIFICA CONFERMA (Ricevuta)
            try:
                # Cerca messaggio di conferma o ricevuta
                receipt = self.page.locator(".bs-Receipt, .st-Receipt")
                receipt.wait_for(state="visible", timeout=8000)
                self.logger.info("✅ Bet CONFIRMED by Bookmaker")
                
                # Chiude ricevuta per essere pronto alla prossima
                done_btn = self.page.locator("button.bs-Receipt_Done")
                if done_btn.is_visible(): done_btn.click()
                
                return True
            except:
                self.logger.error("❌ Bet Confirmation NOT received (Timeout/Error)")
                return False

        except Exception as e:
            self.logger.error(f"Place Bet CRITICAL Error: {e}")
            return False

    def close(self):
        try:
            if self.browser: self.browser.close()
        except: pass

    def recycle_browser(self):
        self.close()
        self._initialized = False
        self.launch_browser()