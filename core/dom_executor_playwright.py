import os
import time
import random
import base64
import threading
from playwright.sync_api import sync_playwright
from core.ai_selector_validator import validate_selector
from core.anti_detect import STEALTH_INJECTION_V4
from core.human_behavior import HumanInput
from core.human_mouse import HumanMouse     # V7.2: Bezier mouse simulation

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
        self.human = None
        self.mouse = None
        self._internal_lock = threading.Lock()

    def set_live_mode(self, enabled: bool):
        self.allow_place = enabled
        mode = "LIVE (REAL MONEY)" if enabled else "DEMO"
        self.logger.warning(f"🔧 Executor set to: {mode}")

    # --- BROWSER GUARDIAN ---
    def launch_browser(self):
        if self._initialized and self.page and not self.page.is_closed():
            return True

        self.logger.info("🌐 [GUARDIAN] Initializing Playwright...")
        if not self.pw:
            self.pw = sync_playwright().start()

        try:
            # 1. Try attaching to Chrome CDP (port 9222)
            self.browser = self.pw.chromium.connect_over_cdp("http://localhost:9222")
            self.ctx = self.browser.contexts[0]

            if self.ctx.pages:
                self.page = self.ctx.pages[0]
                self.logger.info("✅ [GUARDIAN] Attached to existing Chrome session.")
            else:
                self.page = self.ctx.new_page()
                self.logger.info("✅ [GUARDIAN] New tab opened on existing Chrome.")

            self.is_attached = True

        except Exception as e:
            self.logger.info(f"ℹ️ Chrome CDP unavailable ({e}). Launching new browser...")
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
                self.logger.critical(f"❌ [GUARDIAN] Cannot start browser: {e2}")
                # Cleanup Playwright to prevent resource leak
                try:
                    self.pw.stop()
                except Exception:
                    pass
                self.pw = None
                return False

        self.page.add_init_script(STEALTH_INJECTION_V4)
        self.human = HumanInput(self.page, self.logger)
        self.mouse = HumanMouse(self.page, self.logger)
        self._initialized = True
        return True

    def _reset_connection(self):
        """Resets internal connection state to allow full re-initialization.
        Does NOT close the browser process. It only clears references."""
        self._initialized = False
        self.pw = None
        self.browser = None
        self.ctx = None
        self.page = None
        self.human = None
        self.mouse = None

    def close(self):
        """Closes the Playwright connection only, never the user's browser."""
        try:
            if self.browser:
                self.logger.info("🔌 [GUARDIAN] Safe disconnect.")
                self.browser.close()
            if self.pw:
                self.pw.stop()
        except Exception:
            pass
        self._reset_connection()

    def recycle_browser(self) -> bool:
        """Closes and relaunches the browser. Skips if attached to external Chrome."""
        if self.is_attached:
            self.logger.info("♻️ [SKIP] Recycle skipped on persistent session.")
            return True
        self.close()
        return self.launch_browser()

    def _load_selectors(self):
        import yaml
        sel_path = os.path.join(_ROOT_DIR, "config", self.selector_file)
        try:
            with open(sel_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except Exception:
            return {}

    def get_dom_snapshot(self):
        """Returns the full HTML of the current page."""
        if not self.launch_browser():
            return ""
        try:
            return self.page.content()
        except Exception as e:
            self.logger.error(f"DOM snapshot error: {e}")
            return ""

    def take_screenshot_b64(self):
        """Captures a screenshot and returns it as base64."""
        if not self.launch_browser():
            return ""
        try:
            screenshot_bytes = self.page.screenshot(type='jpeg', quality=50)
            return base64.b64encode(screenshot_bytes).decode('utf-8')
        except Exception as e:
            self.logger.error(f"Screenshot error: {e}")
            return ""

    def find_odds(self, match_name, market_name):
        """Finds the real odds on the page. Returns float or None."""
        if not self.launch_browser():
            return None

        self.logger.info(f"🔎 Looking for odds: {match_name} - {market_name}...")

        sels = self._load_selectors()
        odds_selector = sels.get("odds_value", ".gl-ParticipantOddsOnly_Odds")

        try:
            odds_elements = self.page.locator(odds_selector)
            if odds_elements.count() > 0:
                odds_text = odds_elements.first.inner_text().strip()
                return float(odds_text)
        except Exception as e:
            self.logger.warning(f"⚠️ Cannot read odds: {e}")

        return None

    # --- ANTI-TELEPORT & CLICK ---
    def _human_move_and_click(self, locator, timeout=3000):
        """Click with human-like movement. V7.2: Bezier primary, HumanInput fallback. Thread-safe."""
        with self._internal_lock:
            try:
                locator.wait_for(state="visible", timeout=timeout)

                # V7.2: Bezier mouse (most realistic)
                if self.mouse:
                    return self.mouse.click_locator(locator)

                # V6 fallback: HumanInput
                if self.human:
                    return self.human.click_locator(locator)

                # Basic fallback
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
        """Checks the 'Running' tab to verify the bet was placed."""
        self.logger.info("🕵️ [VERIFY] Checking 'Running' bets tab...")
        sels = self._load_selectors()

        btn_bets = self.page.locator(sels.get("my_bets_button", "text=Scommesse")).first
        if not self._human_move_and_click(btn_bets):
            self.logger.warning("⚠️ Cannot open bets menu")
            return False

        time.sleep(1.5)

        btn_running = self.page.locator(sels.get("filter_running", "text=In Corso")).first
        self._human_move_and_click(btn_running)
        time.sleep(1.0)

        team_name = teams.split("-")[0].strip()
        try:
            if self.page.get_by_text(team_name).count() > 0:
                self.logger.info(f"✅ [VERIFY] Bet FOUND: {team_name}")
                self.page.keyboard.press("Escape")
                return True
            else:
                self.logger.error(f"❌ [VERIFY] Bet NOT found: {team_name}")
                self.page.keyboard.press("Escape")
                return False
        except Exception:
            return False

    def verify_bet_success(self, teams, selectors=None):
        """Verifies the bet was accepted (not just clicked).

        Checks 3 signals:
        1. Confirmation message visible
        2. No known error messages visible
        3. Fallback: verify_placement in the bets tab
        """
        if selectors is None:
            selectors = self._load_selectors()

        # 1. Look for confirmation message
        confirm_sel = selectors.get("bet_confirm_msg", "text=Scommessa piazzata")
        try:
            confirm_loc = self.page.locator(confirm_sel).first
            if confirm_loc.is_visible(timeout=3000):
                self.logger.info("✅ [VERIFY] Bet confirmation found.")
                return True
        except Exception:
            pass

        # 2. Look for known error messages
        error_keywords = selectors.get("bet_error_keywords",
                                       ["Rifiutata", "Errore", "Non disponibile", "Quota cambiata"])
        for kw in error_keywords:
            try:
                if self.page.get_by_text(kw).first.is_visible(timeout=500):
                    self.logger.error(f"❌ [VERIFY] Bet rejected: '{kw}' found.")
                    return False
            except Exception:
                pass

        # 3. Fallback: check in the bets tab
        self.logger.info("🔍 [VERIFY] No direct confirmation, checking bets tab...")
        return self.verify_placement(teams)

    def place_bet(self, teams, market, stake):
        self.logger.info(f"🏁 Placing bet: {stake}$ on {teams}")

        if not self.launch_browser():
            return False

        if not self.allow_place:
            self.logger.info("🛡️ [DEMO] Simulation OK.")
            return True

        sels = self._load_selectors()

        # Idle behavior before entering stake (human-like)
        if self.human:
            self.human.idle_fidget()
            time.sleep(random.uniform(0.3, 0.8))

        # Stake input (use HumanInput if available)
        stake_sel = sels.get("stake_input", "input.bs-Stake_Input")
        if self.human:
            if not self.human.type_in_field(stake_sel, str(stake)):
                if not self._safe_fill(stake_sel, str(stake)):
                    self.logger.error("❌ Stake input error")
                    return False
        else:
            if not self._safe_fill(stake_sel, str(stake)):
                self.logger.error("❌ Stake input error")
                return False

        # Human pause: visual recheck before clicking
        time.sleep(random.uniform(0.5, 1.2))

        # Random light scroll (simulates user verifying)
        if self.human and random.random() > 0.5:
            self.human.scroll_random()
            time.sleep(random.uniform(0.2, 0.5))

        # Click place button with human movement
        btn_place = self.page.locator(sels.get("place_button", ".bs-BtnPlace")).first
        if not self._human_move_and_click(btn_place):
            self.logger.error("❌ Place button click error")
            return False

        self.logger.info("⏳ Waiting for processing...")
        time.sleep(random.uniform(2.5, 4.0))

        return self.verify_bet_success(teams, sels)

    def ensure_login(self, selectors=None):
        """Verifies real login: checks balance, otherwise clicks login and waits."""
        if not self.launch_browser():
            return False
        if selectors is None:
            selectors = self._load_selectors()

        balance_sel = selectors.get("balance_selector")
        logged_in_sel = selectors.get("logged_in_indicator")

        # 1. Check if already logged in (balance visible or logged-in indicator)
        for check_sel in [balance_sel, logged_in_sel]:
            if check_sel:
                try:
                    loc = self.page.locator(check_sel).first
                    if loc.is_visible():
                        self.logger.info("Already logged in (indicator visible).")
                        return True
                except Exception:
                    pass

        # 2. Find and click login button
        login_btn = selectors.get("login_button", "text=Login")
        try:
            login_loc = self.page.locator(login_btn).first
            if not login_loc.is_visible():
                self.logger.info("No login button found. Possibly already logged in.")
                return True
        except Exception:
            self.logger.info("No login button found. Possibly already logged in.")
            return True

        if not self._human_move_and_click(login_loc, timeout=5000):
            self.logger.warning("Login button not clickable.")
            return False

        # 3. Wait for login confirmation (balance, indicator, or URL change)
        start_url = self.page.url
        deadline = time.time() + 20

        while time.time() < deadline:
            for check_sel in [balance_sel, logged_in_sel]:
                if check_sel:
                    try:
                        if self.page.locator(check_sel).first.is_visible():
                            self.logger.info("Login completed (indicator visible).")
                            return True
                    except Exception:
                        pass

            try:
                if not self.page.locator(login_btn).first.is_visible():
                    self.logger.info("Login completed (login button disappeared).")
                    return True
            except Exception:
                pass

            if self.page.url != start_url:
                self.logger.info("Login completed (URL changed).")
                time.sleep(1)
                return True

            time.sleep(0.5)

        self.logger.warning("Login: timeout - no confirmation received.")
        return False

    def navigate_to_match(self, teams, selectors=None):
        """Searches for the match in the site search bar with retry."""
        if not self.launch_browser():
            return False
        if not teams:
            self.logger.warning("No team name provided.")
            return False
        if selectors is None:
            selectors = self._load_selectors()

        search_btn = selectors.get("search_button", ".s-SearchButton")
        search_input = selectors.get("search_input", "input.s-SearchInput")

        # Idle behavior before search
        if self.human:
            self.human.idle_fidget()

        # Open search bar
        if not self._human_move_and_click(
            self.page.locator(search_btn).first, timeout=5000
        ):
            self.logger.warning("Search button not found.")
            return False

        time.sleep(random.uniform(0.3, 0.8))

        # Type first team name
        team_name = teams.split("-")[0].strip() if "-" in teams else teams.strip()

        if self.human:
            self.human.type_in_field(search_input, team_name)
        else:
            self._safe_fill(search_input, team_name)

        time.sleep(random.uniform(1.5, 3.0))

        # Click first visible result containing team name
        try:
            results = self.page.get_by_text(team_name)
            for i in range(min(results.count(), 5)):
                result_loc = results.nth(i)
                if result_loc.is_visible():
                    self._human_move_and_click(result_loc)
                    time.sleep(random.uniform(1.5, 3.0))
                    self.logger.info(f"Navigated to match: {teams}")
                    return True
        except Exception as e:
            self.logger.warning(f"Match navigation failed: {e}")

        # Fallback: press Enter on search
        try:
            self.page.keyboard.press("Enter")
            time.sleep(2)
            self.logger.info(f"Navigation via Enter for: {teams}")
            return True
        except Exception:
            pass

        return False

    def check_health(self):
        """Checks if the browser and page are still active and responding."""
        try:
            if self.page is None or self.page.is_closed():
                return False
            self.page.evaluate("() => document.readyState")
            return True
        except Exception:
            return False

    def recover_session(self) -> bool:
        """Attempts to recover the browser session.

        Returns:
            bool: True if recovery succeeds, False otherwise.
        """
        self.logger.warning("🔄 [RECOVERY] Attempting session recovery...")
        try:
            if self.is_attached:
                # Attached mode: do NOT close the external browser process.
                # Just reset internal state and re-attach.
                self._reset_connection()
                return self.launch_browser()

            # Launched mode: properly close and relaunch the browser.
            return self.recycle_browser()

        except Exception as e:
            self.logger.error(f"Session recovery failed: {e}", exc_info=True)
            return False

    # --- V7.2: AUTO-DISCOVERY SCANNER ---
    def scan_page_elements(self, url):
        """Scans the page DOM and returns a list of interactive elements for AI mapping."""
        if not self.launch_browser():
            return None

        self.logger.info(f"🕵️ Scanning DOM structure: {url}")
        try:
            self.page.goto(url, timeout=60000)
            self.page.wait_for_load_state("networkidle")
            time.sleep(4)

            scanner_script = """
            () => {
                const elements = [];
                const interesting = document.querySelectorAll(
                    'button, input, a, div[role="button"], span[role="button"]'
                );
                interesting.forEach(el => {
                    const rect = el.getBoundingClientRect();
                    if (rect.width > 5 && rect.height > 5
                        && el.style.visibility !== 'hidden'
                        && el.style.display !== 'none') {

                        let selector = el.tagName.toLowerCase();
                        if (el.id) {
                            selector += '#' + el.id;
                        } else if (el.className && typeof el.className === 'string') {
                            const valid = el.className.split(' ')
                                .filter(c => c.length > 2 && c.length < 35);
                            if (valid.length > 0) selector += '.' + valid.join('.');
                        }

                        let text = el.innerText || el.placeholder
                            || el.value || el.getAttribute('aria-label') || '';
                        text = text.replace(/\\n/g, ' ').trim().substring(0, 60);

                        if (selector && (text.length > 0 || el.tagName === 'INPUT')) {
                            elements.push({
                                tag: el.tagName.toLowerCase(),
                                text: text,
                                selector: selector,
                                type: el.type || 'n/a',
                                id: el.id || 'n/a'
                            });
                        }
                    }
                });
                return elements.slice(0, 250);
            }
            """
            elements = self.page.evaluate(scanner_script)
            self.logger.info(f"✅ Extracted {len(elements)} candidate elements.")
            return elements
        except Exception as e:
            self.logger.error(f"Scanner error: {e}")
            return []

    def verify_selector_validity(self, selector):
        """Verifies whether a CSS selector exists and is visible on the current page."""
        try:
            if not selector or selector == "NOT_FOUND":
                return False
            loc = self.page.locator(selector).first
            return loc.is_visible(timeout=2000)
        except Exception:
            return False

    def human_click(self, selector):
        """Simulates a human click with delay and hover."""
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
            self.logger.warning(f"Click failed on {selector}: {e}")
            return False

    def human_fill(self, selector, text):
        """Simulates human typing, using HumanInput if available."""
        if not self.launch_browser():
            return False
        try:
            if self.human:
                return self.human.type_in_field(selector, text)
            # Fallback: direct character-by-character typing
            loc = self.page.locator(selector).first
            loc.wait_for(state="visible", timeout=5000)
            loc.click()
            for char in text:
                self.page.keyboard.type(char)
                time.sleep(random.uniform(0.05, 0.15))
            return True
        except Exception as e:
            self.logger.warning(f"Fill failed on {selector}: {e}")
            return False
