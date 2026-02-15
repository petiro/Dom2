import time
import math
import random
from datetime import datetime


class HumanMouse:
    """
    Advanced human mouse simulation with Bezier curves,
    overshoot correction, micro-jitter, and fatigue modeling.
    """

    def __init__(self, page, logger):
        self.page = page
        self.logger = logger
        self.start_session_time = datetime.now()
        self.overshoot_probability = 0.30
        self.fatigue_multiplier = 1.0

    def _calculate_fatigue(self):
        elapsed_mins = (datetime.now() - self.start_session_time).total_seconds() / 60
        self.fatigue_multiplier = 1 + (elapsed_mins * 0.003)

    def _ease_out_quart(self, x):
        return 1 - pow(1 - x, 4)

    def _bezier_curve(self, start, end, control1, control2, t):
        return (
            (1 - t)**3 * start
            + 3 * (1 - t)**2 * t * control1
            + 3 * (1 - t) * t**2 * control2
            + t**3 * end
        )

    def move_to(self, target_x, target_y, steps=None):
        self._calculate_fatigue()

        start_x = random.randint(100, 800)
        start_y = random.randint(100, 600)

        dist = math.hypot(target_x - start_x, target_y - start_y)

        do_overshoot = random.random() < self.overshoot_probability
        if do_overshoot:
            overshoot_amt = random.randint(10, 40)
            angle = math.atan2(target_y - start_y, target_x - start_x)
            virtual_x = target_x + math.cos(angle) * overshoot_amt
            virtual_y = target_y + math.sin(angle) * overshoot_amt
        else:
            virtual_x, virtual_y = target_x, target_y

        control1_x = start_x + (virtual_x - start_x) * random.uniform(0.2, 0.5) + random.randint(-50, 50)
        control1_y = start_y + (virtual_y - start_y) * random.uniform(0.2, 0.5) + random.randint(-50, 50)
        control2_x = start_x + (virtual_x - start_x) * random.uniform(0.6, 0.9) + random.randint(-50, 50)
        control2_y = start_y + (virtual_y - start_y) * random.uniform(0.6, 0.9) + random.randint(-50, 50)

        base_duration = (dist / 1000) * random.uniform(0.8, 1.2) * self.fatigue_multiplier
        base_duration = max(0.4, min(base_duration, 1.8))

        if steps is None:
            steps = int(base_duration * 60)

        for i in range(steps):
            t = i / steps
            ease_t = self._ease_out_quart(t)

            x = self._bezier_curve(start_x, virtual_x, control1_x, control2_x, ease_t)
            y = self._bezier_curve(start_y, virtual_y, control1_y, control2_y, ease_t)

            jitter = random.uniform(-1.5, 1.5) * self.fatigue_multiplier
            try:
                self.page.mouse.move(x + jitter, y + jitter)
            except Exception:
                pass

            time.sleep(base_duration / steps)

        if do_overshoot:
            time.sleep(random.uniform(0.05, 0.15))
            self.page.mouse.move(target_x, target_y, steps=7)

    def click_element(self, selector):
        """Click an element with human-like Bezier mouse movement."""
        try:
            loc = self.page.locator(selector).first
            loc.wait_for(state="visible", timeout=3000)
            box = loc.bounding_box()
            if not box:
                return False

            safe_w = box["width"] * 0.6
            safe_h = box["height"] * 0.6
            target_x = box["x"] + box["width"] / 2 + random.uniform(-safe_w / 2, safe_w / 2)
            target_y = box["y"] + box["height"] / 2 + random.uniform(-safe_h / 2, safe_h / 2)

            self.move_to(target_x, target_y)

            time.sleep(random.uniform(0.05, 0.2))
            self.page.mouse.down()
            time.sleep(random.uniform(0.06, 0.14))
            self.page.mouse.up()
            return True
        except Exception:
            return False

    def click_locator(self, locator):
        """Click a Playwright locator with human-like Bezier mouse movement."""
        try:
            box = locator.bounding_box()
            if not box:
                return False

            safe_w = box["width"] * 0.6
            safe_h = box["height"] * 0.6
            target_x = box["x"] + box["width"] / 2 + random.uniform(-safe_w / 2, safe_w / 2)
            target_y = box["y"] + box["height"] / 2 + random.uniform(-safe_h / 2, safe_h / 2)

            self.move_to(target_x, target_y)

            time.sleep(random.uniform(0.05, 0.2))
            self.page.mouse.down()
            time.sleep(random.uniform(0.06, 0.14))
            self.page.mouse.up()
            return True
        except Exception:
            return False

    def idle_behavior(self):
        """Simulate a user reading or thinking (random mouse movement)."""
        if random.random() < 0.3:
            try:
                self.page.mouse.move(
                    random.randint(200, 600),
                    random.randint(200, 600),
                    steps=15
                )
            except Exception:
                pass
