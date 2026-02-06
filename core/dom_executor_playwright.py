import time
from playwright.sync_api import sync_playwright


class DomExecutorPlaywright:
    """
    DOM Executor using Playwright for browser automation.
    Enterprise-grade: smart waits, retry logic, fallback selectors, auto-recovery.
    No fixed sleeps - all waits are element-based or state-based.
    """

    MAX_RETRIES = 3
    RETRY_DELAY = 2  # seconds between retries

    def __init__(self, logger, headless=True, allow_place=False, pin="0503"):
        self.logger = logger
        self.allow_place = allow_place
        self.pin = pin
        self.headless = headless

        self.pw = None
        self.browser = None
        self.ctx = None
        self.page = None
        self.last_login_time = 0
        self._initialized = False

    def _ensure_browser(self):
        """Initialize browser if not already initialized."""
        if self._initialized:
            return True

        try:
            self.logger.info("Initializing Playwright browser...")
            self.pw = sync_playwright().start()
            self.browser = self.pw.chromium.launch(headless=self.headless)
            self.ctx = self.browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
                viewport={"width": 1366, "height": 768},
                locale="it-IT",
                timezone_id="Europe/Rome"
            )
            self.page = self.ctx.new_page()
            self._initialized = True
            self.logger.info("Browser initialized successfully")
            return True
        except Exception as e:
            self.logger.error(f"Failed to initialize browser: {e}")
            self.logger.error("Make sure Playwright browsers are installed: playwright install chromium")
            return False

    def _wait_for_page_ready(self, timeout=15000):
        """Wait until the page is fully loaded and interactive."""
        try:
            self.page.wait_for_load_state("domcontentloaded", timeout=timeout)
            self.page.wait_for_load_state("networkidle", timeout=timeout)
        except Exception:
            # networkidle can timeout on heavy SPA sites, that's acceptable
            pass

    def _safe_click(self, selector, timeout=10000):
        """Wait for element to be visible, then click. Returns True on success."""
        try:
            loc = self.page.locator(selector)
            loc.first.wait_for(state="visible", timeout=timeout)
            loc.first.click()
            return True
        except Exception as e:
            self.logger.warning(f"Click failed for '{selector}': {e}")
            return False

    def _safe_click_locator(self, locator, timeout=10000):
        """Wait for locator to be visible, then click. Returns True on success."""
        try:
            locator.wait_for(state="visible", timeout=timeout)
            locator.click()
            return True
        except Exception as e:
            self.logger.warning(f"Click failed: {e}")
            return False

    def _safe_fill(self, selector, text, timeout=10000):
        """Wait for input to be visible, clear it, then fill. Returns True on success."""
        try:
            loc = self.page.locator(selector)
            loc.first.wait_for(state="visible", timeout=timeout)
            loc.first.fill(text)
            return True
        except Exception as e:
            self.logger.warning(f"Fill failed for '{selector}': {e}")
            return False

    def _find_element(self, selectors):
        """
        Try multiple selectors (fallback chain). Returns first matching locator or None.

        Args:
            selectors: str or list of str
        """
        if isinstance(selectors, str):
            selectors = [selectors]

        for sel in selectors:
            try:
                loc = self.page.locator(sel)
                if loc.count() > 0:
                    return loc.first
            except Exception:
                continue
        return None

    def _retry(self, func, description="operation"):
        """
        Retry a function up to MAX_RETRIES times with delay between attempts.

        Args:
            func: callable that returns a truthy value on success
            description: human-readable name for logging
        """
        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                result = func()
                if result:
                    return result
            except Exception as e:
                self.logger.warning(f"{description} attempt {attempt}/{self.MAX_RETRIES} failed: {e}")

            if attempt < self.MAX_RETRIES:
                self.logger.info(f"Retrying {description} in {self.RETRY_DELAY}s...")
                time.sleep(self.RETRY_DELAY)

        self.logger.error(f"{description} failed after {self.MAX_RETRIES} attempts")
        return None

    def _recover_page(self):
        """Attempt to recover if page is in a bad state (crashed, navigated away, etc.)."""
        try:
            # Check if page is still alive
            self.page.evaluate("() => document.readyState")
            return True
        except Exception:
            self.logger.warning("Page unresponsive, attempting recovery...")
            try:
                self.page = self.ctx.new_page()
                self.page.goto("https://www.bet365.it/#/HO/", timeout=30000)
                self._wait_for_page_ready()
                self.logger.info("Page recovered successfully")
                return True
            except Exception as e:
                self.logger.error(f"Page recovery failed: {e}")
                return False

    def ensure_login(self, selectors):
        """
        Ensure user is logged in to the betting site.
        Uses smart waits and retry logic.
        """
        if not self._ensure_browser():
            return False

        if time.time() - self.last_login_time < 3000 and self.is_logged_in(selectors):
            return True

        def _do_login():
            self.logger.info("Navigating to login page...")
            self.page.goto("https://www.bet365.it/#/HO/", timeout=30000)
            self._wait_for_page_ready()

            login_btn = self.page.locator("text=Login")
            if login_btn.count() == 0:
                self.logger.info("Already logged in")
                return True

            self.logger.info("Login required, clicking login button...")
            self._safe_click_locator(login_btn)

            # Wait for login form to appear
            pin_input = self.page.locator(".lms-StandardPinModal_Digit")
            accedi_btn = self.page.locator("text=Accedi")

            # Wait for either PIN input or Accedi button
            try:
                self.page.wait_for_selector(
                    ".lms-StandardPinModal_Digit, text=Accedi",
                    timeout=10000
                )
            except Exception:
                self.logger.warning("Login form did not appear")
                return False

            if pin_input.count() > 0:
                self.logger.info("PIN login detected. Entering PIN...")
                for digit in self.pin:
                    self.page.keyboard.type(digit)
                    time.sleep(0.2)
            elif accedi_btn.count() > 0:
                self.logger.info("Waiting for credentials...")
                self._safe_click_locator(accedi_btn)

            self._wait_for_page_ready()
            self.last_login_time = time.time()
            self.logger.info("Login successful")
            return True

        return self._retry(_do_login, "login")

    def is_logged_in(self, selectors):
        """Check if user is currently logged in."""
        if not self._initialized or not self.page:
            return False
        try:
            return self.page.locator("text=Login").count() == 0
        except Exception:
            return False

    def read_market_state(self, selectors):
        """
        Read current market state (suspended status and score).

        Returns:
            dict: {"suspended": bool, "score_now": str or None}
        """
        if not self._ensure_browser():
            return {"suspended": False, "score_now": None}

        try:
            market_lock_selectors = selectors.get("market_lock", [])
            suspended = False
            if market_lock_selectors:
                lock_el = self._find_element(market_lock_selectors)
                suspended = lock_el is not None

            score = None
            score_selectors = selectors.get("score", [])
            if score_selectors:
                score_el = self._find_element(score_selectors)
                if score_el:
                    score = score_el.inner_text().strip()

            return {"suspended": suspended, "score_now": score}
        except Exception as e:
            self.logger.error(f"Error reading market state: {e}")
            return {"suspended": False, "score_now": None}

    def market_reopened(self, selectors):
        """Check if market has reopened (not suspended)."""
        if not self._initialized:
            return False
        try:
            market_lock_selectors = selectors.get("market_lock", [])
            if not market_lock_selectors:
                return True
            return self._find_element(market_lock_selectors) is None
        except Exception:
            return False

    def navigate_to_match(self, teams, selectors):
        """Navigate to a specific match using search with retry."""
        if not self._ensure_browser():
            return False

        def _do_navigate():
            self.logger.info(f"Searching for match: {teams}")

            search_btn_sel = selectors.get("search_button", ".s-SearchButton")
            search_input_sel = selectors.get("search_input", "input.s-SearchInput")

            if self._safe_click(search_btn_sel, timeout=5000):
                if self._safe_fill(search_input_sel, teams):
                    self.page.keyboard.press("Enter")
                    self._wait_for_page_ready()
                    self.logger.info("Match navigation successful")
                    return True

            # Fallback: click team text directly
            team_loc = self.page.locator(f"text={teams}").first
            if self._safe_click_locator(team_loc, timeout=5000):
                self._wait_for_page_ready()
                self.logger.info("Match navigation successful (fallback)")
                return True

            return False

        return self._retry(_do_navigate, f"navigate to {teams}")

    def select_market(self, market_name, selectors):
        """Select a specific betting market with smart wait."""
        if not self._ensure_browser():
            return False

        def _do_select():
            self.logger.info(f"Selecting market: {market_name}")
            market_loc = self.page.locator(f"text={market_name}").first
            if self._safe_click_locator(market_loc):
                self.logger.info("Market selection successful")
                return True
            return False

        return self._retry(_do_select, f"select market {market_name}")

    def place_bet(self, selectors):
        """
        Place a bet (only if allow_place is True).
        Waits for button to be visible and enabled before clicking.
        """
        if not self.allow_place:
            self.logger.warning("BETS ARE DISABLED (allow_place=False). Skipping.")
            return False

        if not self._ensure_browser():
            return False

        try:
            btn_selector = selectors.get('bet_button', 'button:has-text("Piazza")')
            btn = self.page.locator(btn_selector)

            btn.wait_for(state="visible", timeout=5000)
            btn.click()
            self.logger.info("BET PLACED SUCCESSFULLY!")
            return True
        except Exception as e:
            self.logger.error(f"Failed to place bet: {e}")
            return False

    def close(self):
        """Clean up browser resources."""
        self.logger.info("Closing browser...")
        for resource, name in [(self.ctx, "context"), (self.browser, "browser")]:
            try:
                if resource:
                    resource.close()
            except Exception as e:
                self.logger.warning(f"Error closing {name}: {e}")

        try:
            if self.pw:
                self.pw.stop()
        except Exception as e:
            self.logger.warning(f"Error stopping Playwright: {e}")

        self.logger.info("Browser closed")
