import time
import math
import random
import logging
from datetime import datetime
from core.geometry import cubic_bezier
from core.config_paths import TIMEOUT_SHORT

# Movement constants
CONTROL_JITTER = 50
MIN_DURATION = 0.4
MAX_DURATION = 1.8
CLICK_MARGIN = 0.6
VIEWPORT_MARGIN = 50


class HumanMouse:
    def __init__(self, page, logger=None):
        self.page = page
        self.logger = logger or logging.getLogger(self.__class__.__name__)
        self.start_session_time = datetime.now()
        self.overshoot_probability = 0.30
        self.fatigue_multiplier = 1.0

        # Viewport bounds
        try:
            viewport = page.viewport_size
            self.max_w = viewport['width'] if viewport else 1920
            self.max_h = viewport['height'] if viewport else 1080
        except Exception as e:
            self.logger.debug(f"Viewport detection fallback: {e}")
            self.max_w = 1920
            self.max_h = 1080

        # Stateful mouse position — start near center, track across moves
        self.current_x = random.randint(int(self.max_w * 0.4), int(self.max_w * 0.6))
        self.current_y = random.randint(int(self.max_h * 0.4), int(self.max_h * 0.6))

    def _calculate_fatigue(self):
        elapsed_mins = (datetime.now() - self.start_session_time).total_seconds() / 60
        self.fatigue_multiplier = 1 + (elapsed_mins * 0.003)

    def _ease_out_quart(self, x):
        return 1 - pow(1 - x, 4)

    def _clamp(self, val, lo, hi):
        return max(lo, min(val, hi))

    def move_to(self, target_x, target_y, steps=None):
        # Bounds checking
        target_x = self._clamp(target_x, 0, self.max_w)
        target_y = self._clamp(target_y, 0, self.max_h)

        self._calculate_fatigue()

        # Start from current tracked position (no teleportation)
        start_x = self.current_x
        start_y = self.current_y

        dist = math.hypot(target_x - start_x, target_y - start_y)

        # Overshoot logic
        do_overshoot = random.random() < self.overshoot_probability
        virtual_x, virtual_y = target_x, target_y

        if do_overshoot:
            overshoot_amt = random.randint(10, 40)
            angle = math.atan2(target_y - start_y, target_x - start_x)
            virtual_x = self._clamp(target_x + math.cos(angle) * overshoot_amt, 0, self.max_w)
            virtual_y = self._clamp(target_y + math.sin(angle) * overshoot_amt, 0, self.max_h)

        # Control points (clamped to viewport)
        c1_x = self._clamp(
            start_x + (virtual_x - start_x) * random.uniform(0.2, 0.5) + random.randint(-CONTROL_JITTER, CONTROL_JITTER),
            0, self.max_w)
        c1_y = self._clamp(
            start_y + (virtual_y - start_y) * random.uniform(0.2, 0.5) + random.randint(-CONTROL_JITTER, CONTROL_JITTER),
            0, self.max_h)
        c2_x = self._clamp(
            start_x + (virtual_x - start_x) * random.uniform(0.6, 0.9) + random.randint(-CONTROL_JITTER, CONTROL_JITTER),
            0, self.max_w)
        c2_y = self._clamp(
            start_y + (virtual_y - start_y) * random.uniform(0.6, 0.9) + random.randint(-CONTROL_JITTER, CONTROL_JITTER),
            0, self.max_h)

        base_duration = (dist / 1000) * random.uniform(0.8, 1.2) * self.fatigue_multiplier
        base_duration = max(MIN_DURATION, min(base_duration, MAX_DURATION))

        if steps is None:
            steps = int(base_duration * 60)

        for i in range(steps):
            t = i / steps
            ease_t = self._ease_out_quart(t)

            x, y = cubic_bezier((start_x, start_y), (c1_x, c1_y), (c2_x, c2_y), (virtual_x, virtual_y), ease_t)

            jitter = random.uniform(-1.5, 1.5) * self.fatigue_multiplier
            try:
                self.page.mouse.move(x + jitter, y + jitter)
            except Exception as e:
                self.logger.debug(f"Mouse move failed: {e}")
                break
            time.sleep(base_duration / steps)

        if do_overshoot:
            time.sleep(random.uniform(0.05, 0.1))
            self.page.mouse.move(target_x, target_y, steps=5)

        # Update tracked position to final target
        self.current_x = target_x
        self.current_y = target_y

    def click_locator(self, locator):
        """Click a Playwright Locator with human-like behavior."""
        try:
            box = locator.bounding_box()
            if not box:
                return False

            safe_w, safe_h = box["width"] * CLICK_MARGIN, box["height"] * CLICK_MARGIN
            tx = box["x"] + box["width"] / 2 + random.uniform(-safe_w / 2, safe_w / 2)
            ty = box["y"] + box["height"] / 2 + random.uniform(-safe_h / 2, safe_h / 2)

            self.move_to(tx, ty)
            time.sleep(random.uniform(0.05, 0.2))
            self.page.mouse.down()
            time.sleep(random.uniform(0.06, 0.12))
            self.page.mouse.up()
            return True
        except Exception as e:
            self.logger.debug(f"click_locator failed: {e}")
            return False

    def click_element(self, selector):
        """Legacy wrapper for string selector."""
        try:
            loc = self.page.locator(selector).first
            loc.wait_for(state="visible", timeout=TIMEOUT_SHORT)
            return self.click_locator(loc)
        except Exception as e:
            self.logger.debug(f"click_element failed for '{selector}': {e}")
            return False

    def idle_behavior(self):
        if random.random() < 0.3:
            try:
                # Small movement from current position (no teleport)
                offset_x = random.randint(-50, 50)
                offset_y = random.randint(-50, 50)
                new_x = self._clamp(self.current_x + offset_x, VIEWPORT_MARGIN, self.max_w - VIEWPORT_MARGIN)
                new_y = self._clamp(self.current_y + offset_y, VIEWPORT_MARGIN, self.max_h - VIEWPORT_MARGIN)
                self.move_to(new_x, new_y)
            except Exception as e:
                self.logger.debug(f"Idle behavior failed: {e}")
