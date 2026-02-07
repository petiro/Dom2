import os
import sys
import time
import getpass
import platform
import subprocess
from playwright.sync_api import sync_playwright


def close_chrome():
    """Kill all Chrome processes to free the user profile for Playwright persistent context."""
    try:
        if platform.system() == "Windows":
            subprocess.run(["taskkill", "/F", "/IM", "chrome.exe"],
                           capture_output=True, timeout=5)
        else:
            subprocess.run(["pkill", "-f", "chrome"], capture_output=True, timeout=5)
        time.sleep(1)
    except Exception:
        pass


def _detect_chrome_path():
    """Auto-detect Chrome executable path based on OS."""
    if platform.system() == "Windows":
        candidates = [
            os.path.join(os.environ.get("PROGRAMFILES", ""), "Google", "Chrome", "Application", "chrome.exe"),
            os.path.join(os.environ.get("PROGRAMFILES(X86)", ""), "Google", "Chrome", "Application", "chrome.exe"),
            os.path.join(os.environ.get("LOCALAPPDATA", ""), "Google", "Chrome", "Application", "chrome.exe"),
        ]
    elif platform.system() == "Darwin":
        candidates = ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"]
    else:
        candidates = ["/usr/bin/google-chrome", "/usr/bin/chromium-browser", "/usr/bin/chromium"]

    for path in candidates:
        if path and os.path.exists(path):
            return path
    return None


def _detect_chrome_profile():
    """Auto-detect Chrome user data directory based on OS."""
    user = getpass.getuser()
    if platform.system() == "Windows":
        return os.path.join(os.environ.get("LOCALAPPDATA", f"C:\\Users\\{user}\\AppData\\Local"),
                            "Google", "Chrome", "User Data")
    elif platform.system() == "Darwin":
        return os.path.expanduser("~/Library/Application Support/Google/Chrome")
    else:
        return os.path.expanduser("~/.config/google-chrome")


class DomExecutorPlaywright:
    """
    DOM Executor using Playwright for browser automation.
    Uses the user's real Chrome browser (persistent context) with their cookies,
    login sessions, and profile. Falls back to standalone Chromium if Chrome not found.
    Enterprise-grade: smart waits, retry logic, fallback selectors, auto-recovery.
    """

    MAX_RETRIES = 3
    RETRY_DELAY = 2

    def __init__(self, logger, headless=False, allow_place=False, pin="0503",
                 chrome_profile="Default", use_real_chrome=True):
        """
        Args:
            logger: Logger instance
            headless: Run browser headless (must be False for persistent context)
            allow_place: Enable real bet placement
            pin: Login PIN
            chrome_profile: Chrome profile name ("Default", "Profile 1", etc.)
            use_real_chrome: True = use real Chrome with cookies, False = standalone Chromium
        """
        self.logger = logger
        self.allow_place = allow_place
        self.pin = pin
        self.headless = headless
        self.chrome_profile = chrome_profile
        self.use_real_chrome = use_real_chrome

        self.pw = None
        self.browser = None
        self.ctx = None
        self.page = None
        self.last_login_time = 0
        self._initialized = False
        self.healer = None  # Set externally via set_healer()

    def _ensure_browser(self):
        """Initialize browser. Uses real Chrome if available, otherwise standalone Chromium."""
        if self._initialized:
            return True

        try:
            self.pw = sync_playwright().start()

            chrome_path = _detect_chrome_path() if self.use_real_chrome else None
            chrome_profile_dir = _detect_chrome_profile() if self.use_real_chrome else None

            if chrome_path and chrome_profile_dir and os.path.exists(chrome_profile_dir):
                # Use real Chrome with persistent context (cookies, login, history)
                self.logger.info(f"Using real Chrome: {chrome_path}")
                self.logger.info(f"Profile: {chrome_profile_dir} ({self.chrome_profile})")

                self.ctx = self.pw.chromium.launch_persistent_context(
                    chrome_profile_dir,
                    executable_path=chrome_path,
                    headless=False,  # Must be visible for persistent context
                    no_viewport=True,
                    args=[
                        f"--profile-directory={self.chrome_profile}",
                        "--disable-blink-features=AutomationControlled",
                    ],
                    locale="it-IT",
                    timezone_id="Europe/Rome",
                )
                self.browser = None  # No separate browser object with persistent context

                # Use existing page if Chrome already had one open, otherwise create new
                if self.ctx.pages:
                    self.page = self.ctx.pages[0]
                else:
                    self.page = self.ctx.new_page()

                self.logger.info("Real Chrome initialized (your cookies and sessions are active)")
            else:
                # Fallback: standalone Chromium (no cookies, fresh browser)
                if self.use_real_chrome:
                    self.logger.warning("Chrome not found, falling back to standalone Chromium")

                self.browser = self.pw.chromium.launch(headless=self.headless)
                self.ctx = self.browser.new_context(
                    viewport={"width": 1366, "height": 768},
                    locale="it-IT",
                    timezone_id="Europe/Rome",
                )
                self.page = self.ctx.new_page()
                self.logger.info("Standalone Chromium initialized")

            self._initialized = True
            return True

        except Exception as e:
            self.logger.error(f"Failed to initialize browser: {e}")
            if "Target page, context or browser has been closed" in str(e):
                self.logger.error("Close ALL Chrome windows before starting SuperAgent")
            elif "playwright install" in str(e).lower() or "executable doesn't exist" in str(e).lower():
                self.logger.error("Run: playwright install chromium")
            return False

    def _wait_for_page_ready(self, timeout=15000):
        """Wait until the page is fully loaded and interactive."""
        try:
            self.page.wait_for_load_state("domcontentloaded", timeout=timeout)
            self.page.wait_for_load_state("networkidle", timeout=timeout)
        except Exception:
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
        """Wait for input to be visible, then fill. Returns True on success."""
        try:
            loc = self.page.locator(selector)
            loc.first.wait_for(state="visible", timeout=timeout)
            loc.first.fill(text)
            return True
        except Exception as e:
            self.logger.warning(f"Fill failed for '{selector}': {e}")
            return False

    def _find_element(self, selectors):
        """Try multiple selectors (fallback chain). Returns first matching locator or None."""
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
        """Retry a function up to MAX_RETRIES times with delay between attempts."""
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
        """Attempt to recover if page is in a bad state."""
        try:
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
        """Ensure user is logged in. With real Chrome, user may already be logged in via cookies."""
        if not self._ensure_browser():
            return False

        if time.time() - self.last_login_time < 3000 and self.is_logged_in(selectors):
            return True

        def _do_login():
            self.logger.info("Navigating to site...")
            self.page.goto("https://www.bet365.it/#/HO/", timeout=30000)
            self._wait_for_page_ready()

            login_btn = self.page.locator("text=Login")
            if login_btn.count() == 0:
                self.logger.info("Already logged in (cookies active)")
                self.last_login_time = time.time()
                return True

            self.logger.info("Login required, clicking login button...")
            self._safe_click_locator(login_btn)

            try:
                self.page.wait_for_selector(
                    ".lms-StandardPinModal_Digit, text=Accedi",
                    timeout=10000
                )
            except Exception:
                self.logger.warning("Login form did not appear")
                return False

            pin_input = self.page.locator(".lms-StandardPinModal_Digit")
            accedi_btn = self.page.locator("text=Accedi")

            if pin_input.count() > 0:
                self.logger.info("PIN login detected. Entering PIN...")
                for digit in self.pin:
                    self.page.keyboard.type(digit)
                    time.sleep(0.2)
            elif accedi_btn.count() > 0:
                self.logger.info("Credential login...")
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
        """Read current market state (suspended status and score)."""
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
        """Place a bet (only if allow_place is True)."""
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

    def set_healer(self, healer):
        """Connect RPA healer for auto-recovery of broken selectors."""
        self.healer = healer
        self.logger.info("RPA Healer connected to DomExecutor")

    def _load_selectors(self):
        """Load selectors from YAML config."""
        import yaml
        selectors_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                      "config", "selectors.yaml")
        try:
            with open(selectors_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f) or {}
        except Exception:
            return {}

    def safe_click(self, selector_key, element_description=None):
        """
        Click with auto-healing: if selector fails, use RPA Healer to find
        the new selector via DOM scan + AI vision, then retry.
        """
        selectors = self._load_selectors()
        target = selectors.get(selector_key)

        if not target:
            self.logger.warning(f"No selector found for key: {selector_key}")
            return False

        if not self._ensure_browser():
            return False

        try:
            self._safe_click(target)
            return True
        except Exception as e:
            self.logger.warning(f"Click failed for {selector_key}: {e}")

            # Auto-heal if healer is available
            if self.healer and element_description:
                self.logger.info(f"Attempting auto-heal for: {selector_key}")
                new_selector = self.healer.heal_selector(
                    self.page, selector_key, element_description, auto_update=True
                )
                if new_selector:
                    try:
                        self._safe_click(new_selector)
                        self.logger.info(f"Auto-healed click succeeded for: {selector_key}")
                        return True
                    except Exception as e2:
                        self.logger.error(f"Auto-healed click also failed: {e2}")

            return False

    def close(self):
        """Clean up browser resources."""
        self.logger.info("Closing browser...")
        try:
            if self.ctx:
                self.ctx.close()
        except Exception as e:
            self.logger.warning(f"Error closing context: {e}")

        if self.browser:
            try:
                self.browser.close()
            except Exception as e:
                self.logger.warning(f"Error closing browser: {e}")

        try:
            if self.pw:
                self.pw.stop()
        except Exception as e:
            self.logger.warning(f"Error stopping Playwright: {e}")

        self.logger.info("Browser closed")
