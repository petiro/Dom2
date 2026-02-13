"""
DomExecutorPlaywright V4 — Enterprise Stealth Browser Automation.

Features:
  - Bezier mouse movements with stealth profiles
  - Hardware spoofing (Canvas, WebGL, Font)
  - V4 Anti-Detection injection (iframe recursion, MutationObserver)
  - HumanInput integration (stateful mouse, no teleportation)
  - smart_click() self-healing loop with AI trainer + Persistence
  - memory_check() browser recycling
  - CDP connect_over_cdp support
  - Human warmup, curiosity simulation
  - DOM snapshot, Screenshot capture
  - Vision-validated click (anti-honeypot)
  - Dynamic Selector Loading (Multi-Site Support)
"""
import os
import sys
import time
import json
import random
import base64
import getpass
import platform
import subprocess
from playwright.sync_api import sync_playwright

# Assicurati che questi file esistano nel tuo progetto
from core.anti_detect import STEALTH_INJECTION_V4
from core.ai_trainer import AITrainerEngine

# --- CONFIGURAZIONE SAFETY ---
USE_OS_FALLBACK = False  

# --- STEALTH MODE PROFILES ---
STEALTH_PROFILES = {
    "slow": {
        "move_steps_min": 30, "move_steps_max": 60,
        "jitter": 8, "delay_min": 1.0, "delay_max": 2.5,
        "type_delay_min": 0.08, "type_delay_max": 0.25,
        "click_hold_min": 0.08, "click_hold_max": 0.22,
        "warmup_actions": 5,
    },
    "balanced": {
        "move_steps_min": 15, "move_steps_max": 35,
        "jitter": 5, "delay_min": 0.5, "delay_max": 1.5,
        "type_delay_min": 0.04, "type_delay_max": 0.15,
        "click_hold_min": 0.05, "click_hold_max": 0.18,
        "warmup_actions": 3,
    },
    "pro": {
        "move_steps_min": 8, "move_steps_max": 18,
        "jitter": 3, "delay_min": 0.2, "delay_max": 0.6,
        "type_delay_min": 0.02, "type_delay_max": 0.08,
        "click_hold_min": 0.03, "click_hold_max": 0.10,
        "warmup_actions": 1,
    },
}


# --- FUNZIONI HELPER PER IL COMPORTAMENTO UMANO ---

def human_delay(min_s=0.5, max_s=1.5):
    """Simula l'esitazione umana tra un'azione e l'altra."""
    time.sleep(random.uniform(min_s, max_s))


def _bezier_point(t, p0, p1, p2, p3):
    """Cubic Bezier interpolation for a single axis."""
    return ((1 - t)**3 * p0 +
            3 * (1 - t)**2 * t * p1 +
            3 * (1 - t) * t**2 * p2 +
            t**3 * p3)


def human_move_to_element(page, element, mode="balanced"):
    """Move mouse to element with Bezier curve trajectory + jitter."""
    box = element.bounding_box()
    if not box:
        return None, None

    profile = STEALTH_PROFILES.get(mode, STEALTH_PROFILES["balanced"])
    jitter = profile["jitter"]

    target_x = box['x'] + box['width'] / 2 + random.uniform(-jitter, jitter)
    target_y = box['y'] + box['height'] / 2 + random.uniform(-jitter, jitter)

    try:
        vp = page.viewport_size
        start_x = vp["width"] / 2 if vp else 683
        start_y = vp["height"] / 2 if vp else 384
    except Exception:
        start_x, start_y = 683, 384

    cp1_x = start_x + (target_x - start_x) * random.uniform(0.2, 0.5) + random.uniform(-50, 50)
    cp1_y = start_y + (target_y - start_y) * random.uniform(0.0, 0.3) + random.uniform(-30, 30)
    cp2_x = start_x + (target_x - start_x) * random.uniform(0.5, 0.8) + random.uniform(-30, 30)
    cp2_y = start_y + (target_y - start_y) * random.uniform(0.7, 1.0) + random.uniform(-20, 20)

    steps = random.randint(profile["move_steps_min"], profile["move_steps_max"])

    for i in range(1, steps + 1):
        t = i / steps
        bx = _bezier_point(t, start_x, cp1_x, cp2_x, target_x)
        by = _bezier_point(t, start_y, cp1_y, cp2_y, target_y)
        bx += random.uniform(-1.5, 1.5)
        by += random.uniform(-1.5, 1.5)
        page.mouse.move(bx, by)
        time.sleep(random.uniform(0.005, 0.02))

    page.mouse.move(target_x, target_y)
    return target_x, target_y


def close_chrome():
    """Kill all Chrome processes to free the user profile."""
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
    DOM Executor V4 using Playwright for browser automation.
    """

    MAX_RETRIES = 3
    RETRY_DELAY = 2

    def __init__(self, logger, headless=False, allow_place=False, pin="0503",
                 chrome_profile="Default", use_real_chrome=True):
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
        self.healer = None
        self._stealth_mode = "balanced"
        
        # ✅ FIX MULTI-AGENTE
        self.selector_file = "selectors.yaml" 

        self._human_input = None
        self._trainer = None
        self._page_count = 0
        self._last_memory_check = time.time()

    def set_trainer(self, trainer):
        self._trainer = trainer
        self.logger.info("[Executor] AI Trainer connected")

    @property
    def stealth_mode(self) -> str:
        return self._stealth_mode

    @stealth_mode.setter
    def stealth_mode(self, mode: str):
        if mode in STEALTH_PROFILES:
            self._stealth_mode = mode
            self.logger.info(f"Stealth mode set to: {mode}")

    @property
    def _profile(self) -> dict:
        return STEALTH_PROFILES.get(self._stealth_mode, STEALTH_PROFILES["balanced"])

    def set_healer(self, healer):
        self.healer = healer
        self.logger.info("RPA Healer connected")

    @property
    def human(self):
        if self._human_input is None and self.page:
            try:
                from core.human_behavior import HumanInput
                self._human_input = HumanInput(self.page, self.logger)
                self.logger.info("[Executor] HumanInput initialized")
            except ImportError:
                self.logger.warning("[Executor] HumanInput not available")
        return self._human_input

    # --- BROWSER LIFECYCLE ---

    def _ensure_profile_unlocked(self):
        chrome_profile_dir = _detect_chrome_profile() if self.use_real_chrome else None
        if not chrome_profile_dir or not os.path.exists(chrome_profile_dir):
            return
        for lock_name in ("SingletonLock", "SingletonSocket", "SingletonCookie"):
            lock_path = os.path.join(chrome_profile_dir, lock_name)
            if os.path.exists(lock_path):
                try:
                    os.remove(lock_path)
                except Exception:
                    pass

    def launch_browser(self):
        return self._ensure_browser()

    def _ensure_browser(self):
        if self._initialized:
            return True
        try:
            if getattr(sys, "frozen", False):
                from pathlib import Path
                pw_browsers = Path(sys._MEIPASS) / "ms-playwright"
                if pw_browsers.exists():
                    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(pw_browsers)

            self._ensure_profile_unlocked()
            self.pw = sync_playwright().start()

            if os.environ.get("GITHUB_ACTIONS") == "true":
                chrome_path = None
                chrome_profile_dir = None
            else:
                chrome_path = _detect_chrome_path() if self.use_real_chrome else None
                chrome_profile_dir = _detect_chrome_profile() if self.use_real_chrome else None

            stealth_args = [
                "--disable-blink-features=AutomationControlled",
                "--no-default-browser-check",
                "--start-maximized",
                "--disable-infobars"
            ]

            if chrome_path and chrome_profile_dir and os.path.exists(chrome_profile_dir):
                self.logger.info(f"Using real Chrome: {chrome_path}")
                self.ctx = self.pw.chromium.launch_persistent_context(
                    chrome_profile_dir,
                    executable_path=chrome_path,
                    headless=False,
                    viewport=None,
                    no_viewport=True,
                    args=[f"--profile-directory={self.chrome_profile}"] + stealth_args,
                    locale="it-IT",
                    timezone_id="Europe/Rome",
                )
                self.browser = None
                if self.ctx.pages:
                    self.page = self.ctx.pages[0]
                else:
                    self.page = self.ctx.new_page()
                self.page.add_init_script(STEALTH_INJECTION_V4)
            else:
                self.browser = self.pw.chromium.launch(headless=self.headless, args=stealth_args)
                self.ctx = self.browser.new_context(
                    viewport={"width": 1366, "height": 768},
                    locale="it-IT",
                    timezone_id="Europe/Rome",
                )
                self.page = self.ctx.new_page()
                self.page.add_init_script(STEALTH_INJECTION_V4)

            self._human_input = None
            self._initialized = True
            return True
        except Exception as e:
            self.logger.error(f"Failed to initialize browser: {e}")
            return False

    def launch_browser_cdp(self, cdp_url: str = "http://localhost:9222"):
        try:
            if getattr(sys, "frozen", False):
                from pathlib import Path
                pw_browsers = Path(sys._MEIPASS) / "ms-playwright"
                if pw_browsers.exists():
                    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(pw_browsers)
            self.pw = sync_playwright().start()
            self.browser = self.pw.chromium.connect_over_cdp(cdp_url)
            self.ctx = self.browser.contexts[0] if self.browser.contexts else self.browser.new_context()
            self.page = self.ctx.pages[0] if self.ctx.pages else self.ctx.new_page()
            self.page.add_init_script(STEALTH_INJECTION_V4)
            self._human_input = None
            self._initialized = True
            self.logger.info(f"[Executor] Connected to Chrome via CDP: {cdp_url}")
            return True
        except Exception as e:
            self.logger.error(f"[Executor] CDP connect failed: {e}")
            return False

    def close(self):
        self.logger.info("Closing browser...")
        try:
            if self.page:
                try: self.page.close()
                except: pass
            if self.ctx:
                try: self.ctx.close()
                except: pass
            if self.browser:
                try: self.browser.close()
                except: pass
            if self.pw:
                try: self.pw.stop()
                except: pass
        except Exception:
            pass
        self._initialized = False
        self.page = None
        self.ctx = None
        self.browser = None
        self.pw = None
        self._human_input = None
        self.logger.info("Browser closed")

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass

    # --- UTILITIES (Moved up to fix Pylint errors) ---

    def _wait_for_page_ready(self, timeout=15000):
        """Wait until the page is fully loaded and interactive."""
        try:
            self.page.wait_for_load_state("domcontentloaded", timeout=timeout)
            self.page.wait_for_load_state("networkidle", timeout=timeout)
        except Exception:
            pass

    def take_screenshot_b64(self) -> str:
        """Take a screenshot and return it as base64-encoded PNG string."""
        if not self.page:
            return ""
        try:
            screenshot_bytes = self.page.screenshot(type="png")
            return base64.b64encode(screenshot_bytes).decode("utf-8")
        except Exception as e:
            self.logger.error(f"Screenshot failed: {e}")
            return ""

    def _safe_click(self, selector, timeout=10000):
        """Wait for element to be visible, then click with human behavior."""
        try:
            loc = self.page.locator(selector)
            loc.first.wait_for(state="visible", timeout=timeout)
            profile = self._profile
            human_delay(profile["delay_min"] * 0.5, profile["delay_max"] * 0.5)
            x, y = human_move_to_element(self.page, loc.first, mode=self._stealth_mode)
            if x and y:
                human_delay(0.1, 0.3)
                self.page.mouse.down()
                time.sleep(random.uniform(profile["click_hold_min"], profile["click_hold_max"]))
                self.page.mouse.up()
            else:
                loc.first.click()
            return True
        except Exception as e:
            self.logger.warning(f"Click failed for '{selector}': {e}")
            return False

    def _safe_click_locator(self, locator, timeout=10000):
        try:
            locator.wait_for(state="visible", timeout=timeout)
            profile = self._profile
            human_delay(profile["delay_min"] * 0.5, profile["delay_max"] * 0.5)
            x, y = human_move_to_element(self.page, locator, mode=self._stealth_mode)
            if x and y:
                human_delay(0.1, 0.3)
                self.page.mouse.down()
                time.sleep(random.uniform(profile["click_hold_min"], profile["click_hold_max"]))
                self.page.mouse.up()
            else:
                locator.click()
            return True
        except Exception as e:
            self.logger.warning(f"Click failed: {e}")
            return False

    def _safe_fill(self, selector, text, timeout=10000):
        try:
            loc = self.page.locator(selector)
            loc.first.wait_for(state="visible", timeout=timeout)
            human_delay(0.2, 0.5)
            loc.first.focus()
            self.human_type(text)
            return True
        except Exception as e:
            self.logger.warning(f"Fill failed for '{selector}': {e}")
            return False

    def _find_element(self, selectors):
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

    # --- ACTIONS ---

    def go_to_url(self, url: str, timeout: int = 30000) -> bool:
        if not self._ensure_browser():
            return False
        try:
            self.page.goto(url, timeout=timeout)
            self._wait_for_page_ready()
            self._page_count += 1
            return True
        except Exception as e:
            self.logger.error(f"[Executor] go_to_url failed: {e}")
            return False

    def check_and_recycle(self, max_pages: int = 50, max_interval: int = 3600):
        should_recycle = False
        if self._page_count > max_pages:
            self.logger.info(f"[Executor] Memory check: {self._page_count} pages loaded")
            should_recycle = True
        elif time.time() - self._last_memory_check > max_interval:
            self.logger.info("[Executor] Memory check: interval elapsed")
            should_recycle = True

        if should_recycle:
            try:
                self.close()
                time.sleep(2)
                self._ensure_browser()
                self._page_count = 0
                self._last_memory_check = time.time()
                self.logger.info("[Executor] Browser recycled successfully")
                return True
            except Exception as e:
                self.logger.error(f"[Executor] Browser recycling failed: {e}")
                return False
        return False

    def human_warmup(self):
        if not self.page:
            return
        profile = self._profile
        actions = profile.get("warmup_actions", 3)
        self.logger.info(f"[Stealth] Human warmup ({actions} actions)")
        for _ in range(actions):
            action = random.choice(["scroll", "move", "idle"])
            try:
                if action == "scroll":
                    delta = random.randint(-200, 200)
                    self.page.mouse.wheel(0, delta)
                    time.sleep(random.uniform(0.3, 0.8))
                elif action == "move":
                    x = random.randint(100, 1200)
                    y = random.randint(100, 600)
                    self.page.mouse.move(x, y, steps=random.randint(5, 15))
                    time.sleep(random.uniform(0.2, 0.6))
                else: 
                    time.sleep(random.uniform(0.5, 1.5))
            except Exception:
                pass

    def simulate_human_curiosity(self):
        if not self.page:
            return
        self.logger.info("[Stealth] Simulating human curiosity...")
        num_actions = random.randint(2, 5)
        for _ in range(num_actions):
            action = random.choice(["scroll_down", "scroll_up", "hover_random", "micro_move", "pause"])
            try:
                if action == "scroll_down":
                    self.page.mouse.wheel(0, random.randint(100, 400))
                    time.sleep(random.uniform(0.4, 1.0))
                elif action == "scroll_up":
                    self.page.mouse.wheel(0, -random.randint(50, 200))
                    time.sleep(random.uniform(0.3, 0.8))
                elif action == "hover_random":
                    x = random.randint(150, 1100)
                    y = random.randint(100, 500)
                    self.page.mouse.move(x, y, steps=random.randint(10, 25))
                    time.sleep(random.uniform(0.5, 1.2))
                elif action == "micro_move":
                    for _ in range(random.randint(3, 8)):
                        dx = random.uniform(-5, 5)
                        dy = random.uniform(-5, 5)
                        try:
                            self.page.mouse.move(random.randint(300, 800) + dx, random.randint(200, 500) + dy)
                        except Exception:
                            break
                        time.sleep(random.uniform(0.05, 0.15))
                else: 
                    time.sleep(random.uniform(0.8, 2.0))
            except Exception:
                pass

    def human_wait_for(self, selector, timeout=10000):
        if not self.page:
            return None
        try:
            loc = self.page.locator(selector)
            loc.first.wait_for(state="visible", timeout=timeout)
            time.sleep(random.uniform(0.15, 0.4))
            return loc.first
        except Exception:
            return None

    def human_type(self, text):
        if not self.page:
            return
        profile = self._profile
        for char in text:
            self.page.keyboard.type(char)
            delay = random.uniform(profile["type_delay_min"], profile["type_delay_max"])
            if random.random() < 0.05:
                delay += random.uniform(0.3, 0.8)
            time.sleep(delay)

    def vision_validated_click(self, selector, element_description="", vision_learner=None):
        if not self._ensure_browser():
            return False
        loc = self.page.locator(selector)
        try:
            loc.first.wait_for(state="visible", timeout=7000)
        except Exception:
            self.logger.warning(f"[AntiHoneyPot] Element not visible: {selector}")
            return False

        if vision_learner and element_description:
            try:
                screenshot_b64 = self.take_screenshot_b64()
                if screenshot_b64:
                    prompt = (f"Analizza questo screenshot. L'elemento '{element_description}' "
                              f"con selettore '{selector}' e' sicuro da cliccare? "
                              f"Rispondi SOLO 'SAFE' o 'DANGER'.")
                    result = vision_learner.understand_image(screenshot_b64, prompt=prompt, context="anti-honeypot")
                    response_text = str(result) if result else ""
                    if "DANGER" in response_text.upper():
                        self.logger.warning(f"[AntiHoneyPot] DANGER detected: {response_text}")
                        return False
            except Exception:
                pass

        profile = self._profile
        human_delay(profile["delay_min"], profile["delay_max"])
        x, y = human_move_to_element(self.page, loc.first, mode=self._stealth_mode)
        if x and y:
            human_delay(0.1, 0.3)
            self.page.mouse.down()
            time.sleep(random.uniform(profile["click_hold_min"], profile["click_hold_max"]))
            self.page.mouse.up()
            return True
        else:
            loc.first.click()
            return True

    def _load_learned_patterns(self):
        path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "learned_patterns.json")
        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    return json.load(f)
            except: pass
        return []

    def smart_click(self, selector: str, element_description: str = "", max_heal_attempts: int = 2) -> bool:
        if not self._ensure_browser():
            return False

        if self.human and self.human.click(selector):
            return True
        self.logger.warning(f"[SmartClick] Primary selector failed: {selector}")

        # Try healing
        if self._trainer and element_description:
            for attempt in range(1, max_heal_attempts + 1):
                self.logger.info(f"[SmartClick] Healing attempt {attempt}/{max_heal_attempts}")
                new_selector = self._trainer.heal_selector(selector, element_description)
                if new_selector:
                    if self.human and self.human.click(new_selector):
                        self.logger.info(f"[SmartClick] Healed click succeeded: {new_selector}")
                        return True
        return False

    def get_dom_snapshot(self, max_length: int = None) -> str:
        if not self.page:
            return ""
        limit = max_length or AITrainerEngine.DOM_MAX_LENGTH
        try:
            html = self.page.evaluate("""(limit) => {
                const clone = document.documentElement.cloneNode(true);
                const remove = clone.querySelectorAll('script, style, svg, noscript, link[rel=stylesheet]');
                remove.forEach(el => el.remove());
                let html = clone.outerHTML;
                if (html.length > limit) { html = html.substring(0, limit) + '\\n'; }
                return html;
            }""", limit)
            return html
        except Exception:
            return ""

    def highlight_selectors(self, yaml_string):
        import yaml
        if not yaml_string:
            return False
        try:
            selectors = yaml.safe_load(yaml_string)
            if not selectors:
                return False
            js = """
            (selectors) => {
                document.querySelectorAll('[data-ai-highlight]').forEach(el => {
                    el.style.outline = '';
                    el.removeAttribute('data-ai-highlight');
                });
                Object.entries(selectors).forEach(([key, selector]) => {
                    try {
                        const el = document.querySelector(selector);
                        if (el) {
                            el.style.outline = '4px solid red';
                            el.setAttribute('data-ai-highlight', '1');
                        }
                    } catch(e) {}
                });
            }
            """
            self.page.evaluate(js, selectors)
            return True
        except Exception:
            return False

    def memory_check(self):
        import psutil
        try:
            parent = psutil.Process(os.getpid())
            mem = 0
            for child in parent.children(recursive=True):
                if "chrome" in child.name().lower():
                    mem += child.memory_info().rss
            return mem / (1024 * 1024)
        except Exception:
            return 0

    def recycle_browser(self):
        self.close()

    def set_selector_file(self, filename):
        self.selector_file = filename
        self.logger.info(f"📂 Executor: Switch selettori a {filename}")

    def _load_selectors(self):
        import yaml
        file_name = getattr(self, "selector_file", "selectors.yaml")
        selectors_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", file_name)
        try:
            with open(selectors_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f) or {}
        except Exception:
            return {}

    def safe_click(self, selector_key, element_description=None):
        selectors = self._load_selectors()
        target = selectors.get(selector_key)
        if not target:
            return False
        return self._safe_click(target)

    def check_health(self):
        try:
            if not self.page:
                return False
            self.page.evaluate("1+1")
            return True
        except Exception:
            return False

    def recover_session(self):
        try:
            self.close()
            time.sleep(3)
            return self._ensure_browser()
        except Exception:
            sys.exit(1)

    # --- BUSINESS LOGIC ---

    def ensure_login(self, selectors):
        if not self._ensure_browser():
            return False
        if time.time() - self.last_login_time < 3000 and self.is_logged_in(selectors):
            return True
        
        self.logger.info("Navigating to site...")
        self.page.goto("https://www.bet365.it/#/HO/", timeout=30000)
        self._wait_for_page_ready()
        self.human_warmup()

        login_btn = self.page.locator("text=Login")
        if login_btn.count() == 0:
            self.logger.info("Already logged in (cookies active)")
            self.last_login_time = time.time()
            return True

        self.logger.info("Login required...")
        self._safe_click_locator(login_btn)
        
        # Simple wait for login flow completion (manual/automatic)
        self._wait_for_page_ready()
        self.last_login_time = time.time()
        return True

    def is_logged_in(self, selectors):
        if not self._initialized or not self.page:
            return False
        try:
            return self.page.locator("text=Login").count() == 0
        except Exception:
            return False

    def read_market_state(self, selectors):
        return {"suspended": False, "score_now": None}

    def market_reopened(self, selectors):
        return True

    def navigate_to_match(self, teams, selectors):
        if not self._ensure_browser():
            return False
        self.logger.info(f"Searching for match: {teams}")
        self.simulate_human_curiosity()
        
        search_btn_sel = selectors.get("search_button", ".s-SearchButton")
        search_input_sel = selectors.get("search_input", "input.s-SearchInput")

        if self._safe_click(search_btn_sel, timeout=5000):
            human_delay(0.3, 0.7)
            if self._safe_fill(search_input_sel, teams):
                human_delay(0.2, 0.5)
                self.page.keyboard.press("Enter")
                self._wait_for_page_ready()
                self.logger.info("Match navigation successful")
                return True
        return False

    def select_market(self, market_name, selectors):
        if not self._ensure_browser():
            return False
        self.logger.info(f"Selecting market: {market_name}")
        market_loc = self.page.locator(f"text={market_name}").first
        if self._safe_click_locator(market_loc):
            self.logger.info("Market selection successful")
            return True
        return False

    def find_odds(self, match_name, market_name):
        try:
            self.logger.info(f"Ricerca quota: {match_name} -> {market_name}")
            self.page.wait_for_selector(".gl-MarketGroup", timeout=10000)
            market_group = self.page.locator(".gl-MarketGroup", has_text=market_name).first
            odds_element = market_group.locator(".gl-ParticipantOddsOnly_Odds").first
            if odds_element.is_visible():
                str_odds = odds_element.inner_text().strip()
                self.logger.info(f"Quota trovata: {str_odds}")
                return float(str_odds), odds_element
            return 0.0, None
        except Exception:
            return 0.0, None

    def place_bet(self, selectors_or_match, market=None, stake=None):
        if isinstance(selectors_or_match, dict):
            s = selectors_or_match
        else:
            s = {"match": selectors_or_match, "market": market, "stake": stake}
        
        bet_stake = s.get("stake")
        if not bet_stake:
            return False

        try:
            self.logger.info(f"Piazzamento: {bet_stake}")
            odds_value, odds_locator = self.find_odds(s.get("match"), s.get("market"))
            if not odds_locator:
                return False
            odds_locator.click()

            stake_input = self.page.locator(".stb-StakeBox_Input")
            stake_input.wait_for(state="visible", timeout=5000)
            stake_input.click()
            self.page.keyboard.type(str(bet_stake), delay=100)
            
            self.logger.info("[MOCK] Tasto Scommetti pronto")
            return True
        except Exception:
            return False
