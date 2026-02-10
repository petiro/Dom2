"""
DomExecutorPlaywright V4 — Enterprise Stealth Browser Automation.

Features:
  - Bezier mouse movements with stealth profiles
  - Hardware spoofing (Canvas, WebGL, Font)
  - V4 Anti-Detection injection (iframe recursion, MutationObserver)
  - HumanInput integration (stateful mouse, no teleportation)
  - smart_click() self-healing loop with AI trainer
  - memory_check() browser recycling
  - CDP connect_over_cdp support
  - Human warmup, curiosity simulation
  - DOM snapshot, Screenshot capture
  - Vision-validated click (anti-honeypot)
"""
import os
import sys
import time
import random
import math
import base64
import getpass
import platform
import subprocess
from playwright.sync_api import sync_playwright

from core.anti_detect import STEALTH_INJECTION_V4
from core.ai_trainer import AITrainerEngine

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
    """Move mouse to element with Bezier curve trajectory + jitter.

    Modes: 'slow' (Umano Lento), 'balanced' (Bilanciato), 'pro' (Pro/Live).
    """
    box = element.bounding_box()
    if not box:
        return None, None

    profile = STEALTH_PROFILES.get(mode, STEALTH_PROFILES["balanced"])
    jitter = profile["jitter"]

    target_x = box['x'] + box['width'] / 2 + random.uniform(-jitter, jitter)
    target_y = box['y'] + box['height'] / 2 + random.uniform(-jitter, jitter)

    # Get current mouse position (approximate from viewport center if unknown)
    try:
        vp = page.viewport_size
        start_x = vp["width"] / 2 if vp else 683
        start_y = vp["height"] / 2 if vp else 384
    except Exception:
        start_x, start_y = 683, 384

    # Bezier control points with randomness
    cp1_x = start_x + (target_x - start_x) * random.uniform(0.2, 0.5) + random.uniform(-50, 50)
    cp1_y = start_y + (target_y - start_y) * random.uniform(0.0, 0.3) + random.uniform(-30, 30)
    cp2_x = start_x + (target_x - start_x) * random.uniform(0.5, 0.8) + random.uniform(-30, 30)
    cp2_y = start_y + (target_y - start_y) * random.uniform(0.7, 1.0) + random.uniform(-20, 20)

    steps = random.randint(profile["move_steps_min"], profile["move_steps_max"])

    for i in range(1, steps + 1):
        t = i / steps
        bx = _bezier_point(t, start_x, cp1_x, cp2_x, target_x)
        by = _bezier_point(t, start_y, cp1_y, cp2_y, target_y)
        # Add micro-jitter per step
        bx += random.uniform(-1.5, 1.5)
        by += random.uniform(-1.5, 1.5)
        page.mouse.move(bx, by)
        time.sleep(random.uniform(0.005, 0.02))

    # Final precise position
    page.mouse.move(target_x, target_y)
    return target_x, target_y


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
        pass  # Best-effort Chrome cleanup — errors are non-critical


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
    Enterprise-grade Stealth: Bezier movements, Hardware Spoofing,
    V4 Anti-Detection (iframe recursion), HumanInput integration,
    smart_click self-healing, memory_check recycling, CDP connect.
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
        self.healer = None  # Set externally via set_healer()
        self._stealth_mode = "balanced"  # slow | balanced | pro

        # V4: HumanInput integration (lazy init after page is ready)
        self._human_input = None

        # V4: AI Trainer for self-healing
        self._trainer = None

        # V4: Memory check tracking
        self._page_count = 0
        self._last_memory_check = time.time()

    # ------------------------------------------------------------------
    #  V4: Dependency injection
    # ------------------------------------------------------------------
    def set_trainer(self, trainer):
        """Connect AI trainer for self-healing smart_click."""
        self._trainer = trainer
        self.logger.info("[Executor] AI Trainer connected for self-healing")

    # ------------------------------------------------------------------
    #  Stealth mode property
    # ------------------------------------------------------------------
    @property
    def stealth_mode(self) -> str:
        return self._stealth_mode

    @stealth_mode.setter
    def stealth_mode(self, mode: str):
        if mode in STEALTH_PROFILES:
            self._stealth_mode = mode
            self.logger.info(f"Stealth mode set to: {mode}")
        else:
            self.logger.warning(f"Invalid stealth mode: {mode}")

    @property
    def _profile(self) -> dict:
        return STEALTH_PROFILES.get(self._stealth_mode, STEALTH_PROFILES["balanced"])

    def set_healer(self, healer):
        """Connect RPA healer for auto-recovery of broken selectors."""
        self.healer = healer
        self.logger.info("RPA Healer connected to DomExecutor")

    # ------------------------------------------------------------------
    #  V4: HumanInput accessor
    # ------------------------------------------------------------------
    @property
    def human(self):
        """Lazy-init HumanInput from human_behavior module."""
        if self._human_input is None and self.page:
            try:
                from core.human_behavior import HumanInput
                self._human_input = HumanInput(self.page, self.logger)
                self.logger.info("[Executor] HumanInput initialized (stateful mouse)")
            except ImportError:
                self.logger.warning("[Executor] HumanInput not available")
        return self._human_input

    def _ensure_profile_unlocked(self):
        """Remove stale Chrome lock files left by a crash.
        Without this, persistent context launch fails after an unclean exit."""
        chrome_profile_dir = _detect_chrome_profile() if self.use_real_chrome else None
        if not chrome_profile_dir or not os.path.exists(chrome_profile_dir):
            return
        for lock_name in ("SingletonLock", "SingletonSocket", "SingletonCookie"):
            lock_path = os.path.join(chrome_profile_dir, lock_name)
            if os.path.exists(lock_path):
                try:
                    os.remove(lock_path)
                    self.logger.warning(f"Removed stale Chrome lock: {lock_name}")
                except Exception:
                    pass

    def launch_browser(self):
        """Public entry-point: initialize the browser (delegates to _ensure_browser)."""
        return self._ensure_browser()

    def _ensure_browser(self):
        """Initialize browser with Stealth arguments, V4 Anti-Detection, and Hardware Spoofing."""
        if self._initialized:
            return True

        try:
            # Remove stale lock files from previous crash (critical for H24)
            self._ensure_profile_unlocked()

            self.pw = sync_playwright().start()

            # Se siamo su GitHub Actions, NON usare il Chrome di sistema
            if os.environ.get("GITHUB_ACTIONS") == "true":
                chrome_path = None
                chrome_profile_dir = None
            else:
                chrome_path = _detect_chrome_path() if self.use_real_chrome else None
                chrome_profile_dir = _detect_chrome_profile() if self.use_real_chrome else None

            # Argomenti Stealth Avanzati
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
                    viewport=None,   # Fondamentale per fingerprint reale
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

                # V4: Full stealth injection (replaces old webdriver + hardware spoof)
                self.page.add_init_script(STEALTH_INJECTION_V4)

                self.logger.info("Real Chrome initialized with V4 Ghost Protocol Stealth")
            else:
                if self.use_real_chrome:
                    self.logger.warning("Chrome not found, falling back to standalone Chromium")

                self.browser = self.pw.chromium.launch(headless=self.headless, args=stealth_args)
                self.ctx = self.browser.new_context(
                    viewport={"width": 1366, "height": 768},
                    locale="it-IT",
                    timezone_id="Europe/Rome",
                )
                self.page = self.ctx.new_page()

                # V4: Full stealth injection
                self.page.add_init_script(STEALTH_INJECTION_V4)
                self.logger.info("Standalone Chromium initialized with V4 Ghost Protocol Stealth")

            # Reset HumanInput for new page
            self._human_input = None

            self._initialized = True
            return True

        except Exception as e:
            self.logger.error(f"Failed to initialize browser: {e}")
            return False

    # ------------------------------------------------------------------
    #  V4: CDP Connect (attach to desktop-opened Chrome)
    # ------------------------------------------------------------------
    def launch_browser_cdp(self, cdp_url: str = "http://localhost:9222"):
        """Connect to an already-running Chrome via CDP.
        Use this when Chrome is opened from desktop (HumanOS).
        """
        try:
            self.pw = sync_playwright().start()
            self.browser = self.pw.chromium.connect_over_cdp(cdp_url)
            self.ctx = self.browser.contexts[0] if self.browser.contexts else self.browser.new_context()
            self.page = self.ctx.pages[0] if self.ctx.pages else self.ctx.new_page()

            # V4: Full stealth injection
            self.page.add_init_script(STEALTH_INJECTION_V4)

            # Reset HumanInput for new page
            self._human_input = None

            self._initialized = True
            self.logger.info(f"[Executor] Connected to Chrome via CDP: {cdp_url}")
            return True
        except Exception as e:
            self.logger.error(f"[Executor] CDP connect failed: {e}")
            return False

    # ------------------------------------------------------------------
    #  V4: Navigate to URL
    # ------------------------------------------------------------------
    def go_to_url(self, url: str, timeout: int = 30000) -> bool:
        """Navigate to a URL with stealth injection."""
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

    # ------------------------------------------------------------------
    #  V4: Page Count Recycling
    # ------------------------------------------------------------------
    def check_and_recycle(self, max_pages: int = 50, max_interval: int = 3600):
        """Check if browser needs recycling based on page count or time interval."""
        should_recycle = False

        if self._page_count > max_pages:
            self.logger.info(f"[Executor] Memory check: {self._page_count} pages loaded — recycling")
            should_recycle = True
        elif time.time() - self._last_memory_check > max_interval:
            self.logger.info("[Executor] Memory check: interval elapsed — recycling")
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

    # ------------------------------------------------------------------
    #  Stealth: Human Warmup
    # ------------------------------------------------------------------
    def human_warmup(self):
        """Simulate human warm-up after page load: scroll, move mouse, idle.
        Makes the browser fingerprint look natural before any interaction."""
        if not self.page:
            return
        profile = self._profile
        actions = profile.get("warmup_actions", 3)

        self.logger.info(f"[Stealth] Human warmup ({actions} actions, mode={self._stealth_mode})")

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
                else:  # idle
                    time.sleep(random.uniform(0.5, 1.5))
            except Exception as e:
                self.logger.warning(f"[Stealth] Warmup action failed: {e}")

    # ------------------------------------------------------------------
    #  Stealth: Simulate Human Curiosity
    # ------------------------------------------------------------------
    def simulate_human_curiosity(self):
        """Random scrolling, fake hovers, idle micro-movements.
        Call before important actions to look like a real user exploring."""
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
                    # Hover over a random visible element
                    x = random.randint(150, 1100)
                    y = random.randint(100, 500)
                    self.page.mouse.move(x, y, steps=random.randint(10, 25))
                    time.sleep(random.uniform(0.5, 1.2))
                elif action == "micro_move":
                    # Tiny mouse movements (idle fidgeting)
                    for _ in range(random.randint(3, 8)):
                        dx = random.uniform(-5, 5)
                        dy = random.uniform(-5, 5)
                        try:
                            self.page.mouse.move(
                                random.randint(300, 800) + dx,
                                random.randint(200, 500) + dy
                            )
                        except Exception:
                            break  # page likely dead, stop micro-moves
                        time.sleep(random.uniform(0.05, 0.15))
                else:  # pause
                    time.sleep(random.uniform(0.8, 2.0))
            except Exception as e:
                self.logger.warning(f"[Stealth] Curiosity action failed: {e}")

    # ------------------------------------------------------------------
    #  Stealth: Smart Human Wait
    # ------------------------------------------------------------------
    def human_wait_for(self, selector, timeout=10000):
        """Wait for element with human reaction time delay added."""
        if not self.page:
            return None
        try:
            loc = self.page.locator(selector)
            loc.first.wait_for(state="visible", timeout=timeout)
            # Human reaction time: 150-400ms
            time.sleep(random.uniform(0.15, 0.4))
            return loc.first
        except Exception:
            return None

    # ------------------------------------------------------------------
    #  Stealth: Human Typing (biological rhythm)
    # ------------------------------------------------------------------
    def human_type(self, text):
        """Type text with per-character delay simulating biological rhythm."""
        if not self.page:
            return
        profile = self._profile
        for char in text:
            self.page.keyboard.type(char)
            delay = random.uniform(profile["type_delay_min"], profile["type_delay_max"])
            # Occasional longer pause (thinking)
            if random.random() < 0.05:
                delay += random.uniform(0.3, 0.8)
            time.sleep(delay)

    # ------------------------------------------------------------------
    #  Anti-HoneyPot: Vision-Validated Click
    # ------------------------------------------------------------------
    def vision_validated_click(self, selector, element_description="", vision_learner=None):
        """Click only after AI vision confirms the element is safe (not a honeypot).
        Falls back to normal click if vision is unavailable."""
        if not self._ensure_browser():
            return False

        loc = self.page.locator(selector)
        try:
            loc.first.wait_for(state="visible", timeout=7000)
        except Exception:
            self.logger.warning(f"[AntiHoneyPot] Element not visible: {selector}")
            return False

        # If vision learner available, validate before clicking
        if vision_learner and element_description:
            try:
                screenshot_b64 = self.take_screenshot_b64()
                if screenshot_b64:
                    prompt = (
                        f"Analizza questo screenshot. L'elemento '{element_description}' "
                        f"con selettore '{selector}' e' sicuro da cliccare? "
                        f"Potrebbe essere un honeypot o un elemento nascosto/trappola? "
                        f"Rispondi SOLO 'SAFE' o 'DANGER' seguito da una breve motivazione."
                    )
                    result = vision_learner.understand_image(screenshot_b64, prompt=prompt, context="anti-honeypot")
                    response_text = str(result) if result else ""
                    if "DANGER" in response_text.upper():
                        self.logger.warning(f"[AntiHoneyPot] DANGER detected for {selector}: {response_text}")
                        return False
                    self.logger.info(f"[AntiHoneyPot] Element validated as SAFE: {selector}")
            except Exception as e:
                self.logger.warning(f"[AntiHoneyPot] Vision check failed, proceeding: {e}")

        # Proceed with human click
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

    # ------------------------------------------------------------------
    #  V4: Smart Click (self-healing loop)
    # ------------------------------------------------------------------
    def smart_click(self, selector: str, element_description: str = "",
                    max_heal_attempts: int = 2) -> bool:
        """Click with self-healing: if selector fails, use AI trainer
        to find a new selector via DOM + vision analysis, then retry.

        Args:
            selector: CSS selector to click
            element_description: human description of the target element
            max_heal_attempts: max AI healing retries
        """
        if not self._ensure_browser():
            return False

        # Try normal click first (via HumanInput for stateful mouse)
        if self.human and self.human.click(selector):
            return True
        self.logger.warning(f"[SmartClick] Primary selector failed: {selector} — attempting healing.")

        # Self-healing loop
        if self._trainer and element_description:
            for attempt in range(1, max_heal_attempts + 1):
                self.logger.info(f"[SmartClick] Healing attempt {attempt}/{max_heal_attempts}")
                new_selector = self._trainer.heal_selector(selector, element_description)
                if new_selector:
                    if self.human and self.human.click(new_selector):
                        self.logger.info(f"[SmartClick] Healed click succeeded: {new_selector}")
                        return True
                    self.logger.warning(f"[SmartClick] Healed selector also failed: {new_selector}")
                    selector = new_selector  # use as base for next heal attempt

        # Fallback: try old healer if available
        if self.healer and element_description:
            self.logger.info("[SmartClick] Trying legacy RPA Healer...")
            new_selector = self.healer.heal_selector(
                self.page, selector, element_description, auto_update=True
            )
            if new_selector:
                try:
                    self._safe_click(new_selector)
                    return True
                except Exception as e:
                    self.logger.warning(f"[SmartClick] Legacy healer click also failed: {e}")

        self.logger.error(f"[SmartClick] All attempts failed for: {selector}")
        return False

    # ------------------------------------------------------------------
    #  DOM Snapshot
    # ------------------------------------------------------------------
    def get_dom_snapshot(self, max_length: int = None) -> str:
        """Get cleaned DOM snapshot: removes script/style/svg, truncated to max_length chars."""
        if not self.page:
            return ""
        limit = max_length or AITrainerEngine.DOM_MAX_LENGTH
        try:
            html = self.page.evaluate("""(limit) => {
                const clone = document.documentElement.cloneNode(true);
                // Remove noisy elements
                const remove = clone.querySelectorAll('script, style, svg, noscript, link[rel=stylesheet]');
                remove.forEach(el => el.remove());
                let html = clone.outerHTML;
                if (html.length > limit) {
                    html = html.substring(0, limit) + '\\n<!-- TRONCATO -->';
                }
                return html;
            }""", limit)
            return html
        except Exception as e:
            self.logger.error(f"DOM snapshot failed: {e}")
            return ""

    # ------------------------------------------------------------------
    #  Highlight Selectors (Visual Feedback)
    # ------------------------------------------------------------------
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
                // Reset highlights precedenti
                document.querySelectorAll('[data-ai-highlight]').forEach(el => {
                    el.style.outline = '';
                    el.removeAttribute('data-ai-highlight');
                    const label = el.querySelector('.ai-label');
                    if(label) label.remove();
                });

                Object.entries(selectors).forEach(([key, selector]) => {
                    try {
                        const el = document.querySelector(selector);
                        if (el) {
                            el.style.outline = '4px solid red';
                            el.style.outlineOffset = '-2px';
                            el.setAttribute('data-ai-highlight', '1');
                            
                            // Etichetta
                            const label = document.createElement('div');
                            label.className = 'ai-label';
                            label.innerText = key;
                            label.style.cssText = "position:absolute; background:red; color:white; font-size:10px; padding:2px; top:-15px; left:0; z-index:9999;";
                            el.appendChild(label);
                        }
                    } catch(e) {}
                });
            }
            """
            self.page.evaluate(js, selectors)
            return True
        except Exception as e:
            self.logger.error(f"Highlight error: {e}")
            return False

    # ------------------------------------------------------------------
    #  Memory Check & Browser Recycle
    # ------------------------------------------------------------------
    def memory_check(self):
        """Return Chrome child process memory usage in MB."""
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
        """Close and reopen browser to free RAM."""
        self.logger.info("Recycling Browser (Memory Cleanup)...")
        try:
            if self.ctx:
                self.ctx.close()
            if self.browser and hasattr(self.browser, 'close'):
                self.browser.close()
        except Exception as e:
            self.logger.warning(f"Error during browser recycle cleanup: {e}")
        self._initialized = False
        self.ctx = None
        self.browser = None
        self.page = None
        self._human_input = None
        time.sleep(2)
        self._ensure_browser()

    # ------------------------------------------------------------------
    #  Screenshot to Base64
    # ------------------------------------------------------------------
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

    # ------------------------------------------------------------------
    #  Core: Find Odds (for BetWorker)
    # ------------------------------------------------------------------
    def find_odds(self, match, market):
        """Extract odds value for a given match/market from the current page.
        Returns float odds or None if not found."""
        if not self._ensure_browser():
            return None
        try:
            # Look for odds element near the market text
            odds_loc = self.page.locator(f"text={market}").first
            odds_loc.wait_for(state="visible", timeout=5000)
            # Try to find the adjacent odds value
            parent = odds_loc.locator("xpath=..")
            odds_text = parent.locator(".odds, .price, [class*='odds'], [class*='price']").first.inner_text()
            return float(odds_text.replace(",", ".").strip())
        except Exception as e:
            self.logger.warning(f"find_odds failed for {match}/{market}: {e}")
            return None

    # ------------------------------------------------------------------
    #  Core: Place Bet
    # ------------------------------------------------------------------
    def place_bet(self, selectors):
        """Place a bet using Human-Style interaction (Bezier + Split Click)."""
        if not self.allow_place:
            self.logger.warning("BETS ARE DISABLED (allow_place=False). Skipping.")
            return False

        if not self._ensure_browser():
            return False

        try:
            btn_selector = selectors.get('bet_button', 'button:has-text("Piazza")')
            btn = self.page.locator(btn_selector)
            btn.wait_for(state="visible", timeout=7000)

            profile = self._profile
            self.logger.info(f"Simulating human movement to bet button (mode={self._stealth_mode})...")

            # 1. Simulate curiosity before the big action
            if self._stealth_mode == "slow":
                self.simulate_human_curiosity()

            # 2. Delay di esitazione pre-movimento
            human_delay(profile["delay_min"], profile["delay_max"])

            # 3. Bezier movement to element
            x, y = human_move_to_element(self.page, btn, mode=self._stealth_mode)

            if x and y:
                # 4. Micro-esitazione pre-click
                human_delay(0.1, 0.3)

                # 5. Click umano: down -> micro-pausa -> up
                self.page.mouse.down()
                time.sleep(random.uniform(profile["click_hold_min"], profile["click_hold_max"]))
                self.page.mouse.up()

                self.logger.info("BET PLACED SUCCESSFULLY (Human Interaction)!")
                return True

            return False
        except Exception as e:
            self.logger.error(f"Failed to place bet: {e}")
            return False

    def _wait_for_page_ready(self, timeout=15000):
        """Wait until the page is fully loaded and interactive."""
        try:
            self.page.wait_for_load_state("domcontentloaded", timeout=timeout)
            self.page.wait_for_load_state("networkidle", timeout=timeout)
        except Exception:
            pass

    def _safe_click(self, selector, timeout=10000):
        """Wait for element to be visible, then click with human behavior. Returns True on success."""
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
        """Wait for locator to be visible, then click with human behavior."""
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
        """Wait for input to be visible, then fill with human typing. Returns True on success."""
        try:
            loc = self.page.locator(selector)
            loc.first.wait_for(state="visible", timeout=timeout)
            human_delay(0.2, 0.5)
            # Use human_type for biological rhythm
            loc.first.focus()
            self.human_type(text)
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
                # V4: Full stealth injection on new page
                self.page.add_init_script(STEALTH_INJECTION_V4)
                self.page.goto("https://www.bet365.it/#/HO/", timeout=30000)
                self._wait_for_page_ready()
                # Reset HumanInput for new page
                self._human_input = None
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

            # Warmup after page load
            self.human_warmup()

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
                    profile = self._profile
                    time.sleep(random.uniform(profile["type_delay_min"], profile["type_delay_max"]))
                    self.page.keyboard.type(digit)
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
        """Navigate to a specific match using search with human-like interaction."""
        if not self._ensure_browser():
            return False

        def _do_navigate():
            self.logger.info(f"Searching for match: {teams}")

            # Simulate curiosity before searching
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

            team_loc = self.page.locator(f"text={teams}").first
            if self._safe_click_locator(team_loc, timeout=5000):
                self._wait_for_page_ready()
                self.logger.info("Match navigation successful (fallback)")
                return True
            return False

        return self._retry(_do_navigate, f"navigate to {teams}")

    def select_market(self, market_name, selectors):
        """Select a specific betting market with human-like interaction."""
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
        """Click with auto-healing: if selector fails, use RPA Healer to find
        the new selector via DOM scan + AI vision, then retry."""
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

    def check_health(self):
        """Check if the browser is still responding."""
        try:
            if not self.page:
                return False
            self.page.evaluate("1+1")
            return True
        except Exception:
            self.logger.error("Browser not responding — health check failed")
            return False

    def recover_session(self):
        """Close everything and re-launch the browser.
        Returns True on success, triggers hard restart on total failure."""
        try:
            self.close()
            time.sleep(3)
            ok = self._ensure_browser()
            if not ok:
                raise Exception("Browser relaunch failed")
            self.logger.info("Browser session recovered successfully")
            return True
        except Exception as e:
            self.logger.critical(f"Browser unrecoverable: {e} — triggering restart")
            os.execv(sys.executable, [sys.executable] + sys.argv)

    def handle_signal(self, signal_data: dict):
        """Handle a parsed Telegram signal — navigate, select market, place bet.
        Called from the main thread via Qt Signal/Slot."""
        teams = signal_data.get("teams", "")
        market = signal_data.get("market", "")
        self.logger.info(f"handle_signal: {teams} / {market}")

        if not self._ensure_browser():
            self.logger.error("handle_signal: browser not available")
            return False

        selectors = self._load_selectors()

        if not self.ensure_login(selectors):
            self.logger.error("handle_signal: login failed")
            return False

        if teams and not self.navigate_to_match(teams, selectors):
            self.logger.error(f"handle_signal: could not find match {teams}")
            return False

        if market and not self.select_market(market, selectors):
            self.logger.error(f"handle_signal: could not select market {market}")
            return False

        return self.place_bet(selectors)

    def close(self):
        """Clean up browser resources (page, context, browser, playwright)."""
        self.logger.info("Closing browser...")
        try:
            if self.page:
                try:
                    self.page.close()
                except Exception:
                    pass
            if self.ctx:
                try:
                    self.ctx.close()
                except Exception:
                    pass
            if self.browser:
                try:
                    self.browser.close()
                except Exception:
                    pass
            if self.pw:
                try:
                    self.pw.stop()
                except Exception:
                    pass
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
        """Destructor — ensure browser resources are freed."""
        try:
            self.close()
        except Exception:
            pass
