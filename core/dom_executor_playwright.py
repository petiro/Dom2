import time
import random
from playwright.sync_api import sync_playwright


def human_delay(min_s=0.3, max_s=1.5):
    """Random delay to simulate human reaction time"""
    time.sleep(random.uniform(min_s, max_s))


def human_typing_delay():
    """Random delay between keystrokes (human typing speed ~40-80 WPM)"""
    time.sleep(random.uniform(0.05, 0.22))


class DomExecutorPlaywright:
    """
    DOM Executor using Playwright for browser automation.
    All interactions use human-like timing: random delays, letter-by-letter typing,
    and smart waits for page elements instead of fixed sleeps.
    """

    def __init__(self, logger, headless=True, allow_place=False, pin="0503"):
        self.logger = logger
        self.allow_place = allow_place
        self.pin = pin
        self.headless = headless

        # Lazy initialization - will be set on first use
        self.pw = None
        self.browser = None
        self.ctx = None
        self.page = None
        self.last_login_time = 0
        self._initialized = False

    def _ensure_browser(self):
        """
        Initialize browser if not already initialized.
        This is called lazily on first use to avoid startup crashes.
        """
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

    def _human_type(self, selector, text):
        """Type text letter by letter with human-like delays"""
        locator = self.page.locator(selector)
        locator.click()
        human_delay(0.2, 0.5)

        for char in text:
            self.page.keyboard.type(char)
            human_typing_delay()

    def _human_click(self, locator_or_selector):
        """Click with a small human-like pause before and after"""
        human_delay(0.2, 0.8)

        if isinstance(locator_or_selector, str):
            self.page.locator(locator_or_selector).click()
        else:
            locator_or_selector.click()

        human_delay(0.1, 0.4)

    def _wait_for_page_ready(self, timeout=15000):
        """Wait until the page is fully loaded and interactive"""
        try:
            self.page.wait_for_load_state("domcontentloaded", timeout=timeout)
            # Also wait for network to be mostly quiet
            self.page.wait_for_load_state("networkidle", timeout=timeout)
        except Exception:
            # networkidle can timeout on heavy SPA sites, that's OK
            pass
        human_delay(0.5, 1.5)

    def ensure_login(self, selectors):
        """
        Ensure user is logged in to the betting site.
        Handles both PIN and credential-based login.
        """
        if not self._ensure_browser():
            return False

        # If logged in recently, skip
        if time.time() - self.last_login_time < 3000 and self.is_logged_in(selectors):
            return True

        try:
            self.logger.info("Navigating to login page...")
            self.page.goto("https://www.bet365.it/#/HO/", timeout=30000)
            self._wait_for_page_ready()

            # Check if login is needed
            login_btn = self.page.locator("text=Login")
            if login_btn.count() > 0:
                self.logger.info("Login required, clicking login button...")
                self._human_click(login_btn)
                human_delay(1.0, 2.5)

                # Handle PIN login
                pin_input = self.page.locator(".lms-StandardPinModal_Digit")
                if pin_input.count() > 0:
                    self.logger.info("PIN login detected. Entering PIN...")
                    human_delay(0.5, 1.2)
                    for digit in self.pin:
                        self.page.keyboard.type(digit)
                        # Human types PIN digits with variable speed
                        time.sleep(random.uniform(0.15, 0.45))
                else:
                    # Wait for credentials autofill or manual entry
                    self.logger.info("Waiting for credentials (autofill or manual)...")
                    self.page.wait_for_selector("text=Accedi", timeout=30000)
                    self._human_click("text=Accedi")

                human_delay(1.0, 2.0)
                self.last_login_time = time.time()
                self.logger.info("Login successful")
                return True
            else:
                self.logger.info("Already logged in")
                return True

        except Exception as e:
            self.logger.error(f"Login failed: {e}")
            return False

    def is_logged_in(self, selectors):
        """Check if user is currently logged in"""
        if not self._initialized or not self.page:
            return False
        try:
            return self.page.locator("text=Login").count() == 0
        except Exception:
            return False

    def read_market_state(self, selectors):
        """
        Read current market state (suspended status and score)

        Returns:
            dict: {"suspended": bool, "score_now": str or None}
        """
        if not self._ensure_browser():
            return {"suspended": False, "score_now": None}

        try:
            # Check if market is locked/suspended
            market_lock_selectors = selectors.get("market_lock", [])
            suspended = False
            if market_lock_selectors:
                suspended = self.page.locator(",".join(market_lock_selectors)).count() > 0

            # Get current score
            score = None
            score_selectors = selectors.get("score", [])
            if score_selectors:
                loc = self.page.locator(",".join(score_selectors))
                if loc.count() > 0:
                    score = loc.first.inner_text().strip()

            return {"suspended": suspended, "score_now": score}
        except Exception as e:
            self.logger.error(f"Error reading market state: {e}")
            return {"suspended": False, "score_now": None}

    def market_reopened(self, selectors):
        """Check if market has reopened (not suspended)"""
        if not self._initialized:
            return False
        try:
            market_lock_selectors = selectors.get("market_lock", [])
            if not market_lock_selectors:
                return True
            return self.page.locator(",".join(market_lock_selectors)).count() == 0
        except Exception:
            return False

    def navigate_to_match(self, teams, selectors):
        """
        Navigate to a specific match with human-like search behavior.
        """
        if not self._ensure_browser():
            return False

        try:
            self.logger.info(f"Searching for match: {teams}")

            # Try using search button if available
            search_btn = self.page.locator(selectors.get("search_button", ".s-SearchButton"))
            if search_btn.count() > 0:
                self._human_click(search_btn)
                human_delay(0.3, 0.8)

                # Type team name letter by letter
                search_input = selectors.get("search_input", "input.s-SearchInput")
                self._human_type(search_input, teams)

                human_delay(0.5, 1.0)
                self.page.keyboard.press("Enter")
                self._wait_for_page_ready()
            else:
                # Fallback: search for team text directly
                human_delay(0.5, 1.5)
                self._human_click(self.page.locator(f"text={teams}").first)
                self._wait_for_page_ready()

            self.logger.info("Match navigation successful")
            return True
        except Exception as e:
            self.logger.error(f"Navigation failed: {e}")
            return False

    def select_market(self, market_name, selectors):
        """
        Select a specific betting market with human-like click.
        """
        if not self._ensure_browser():
            return False

        try:
            self.logger.info(f"Selecting market: {market_name}")

            # Wait for market to be visible, then click
            market_loc = self.page.locator(f"text={market_name}").first
            market_loc.wait_for(state="visible", timeout=10000)
            self._human_click(market_loc)
            human_delay(0.3, 0.8)

            self.logger.info("Market selection successful")
            return True
        except Exception as e:
            self.logger.error(f"Market selection failed: {e}")
            return False

    def place_bet(self, selectors):
        """
        Place a bet (only if allow_place is True).
        Uses human-like timing for the critical click.
        """
        if not self.allow_place:
            self.logger.warning("BETS ARE DISABLED (allow_place=False). Skipping real click.")
            return False

        if not self._ensure_browser():
            return False

        try:
            btn_selector = selectors.get('bet_button', 'button:has-text("Piazza")')
            btn = self.page.locator(btn_selector)

            # Wait for button to be visible and enabled
            btn.wait_for(state="visible", timeout=5000)
            human_delay(0.5, 1.5)

            btn.click()
            self.logger.info("BET PLACED SUCCESSFULLY!")
            human_delay(1.0, 2.0)
            return True
        except Exception as e:
            self.logger.error(f"Failed to place bet: {e}")
            return False

    def close(self):
        """Clean up browser resources"""
        self.logger.info("Closing browser...")
        try:
            if self.ctx:
                self.ctx.close()
        except Exception as e:
            self.logger.warning(f"Error closing context: {e}")

        try:
            if self.browser:
                self.browser.close()
        except Exception as e:
            self.logger.warning(f"Error closing browser: {e}")

        try:
            if self.pw:
                self.pw.stop()
        except Exception as e:
            self.logger.warning(f"Error stopping Playwright: {e}")

        self.logger.info("Browser closed")
