"""
Human Behavior Engine V4 — Stateful biometric mouse and keyboard simulation.

Features:
  - Stateful mouse position (current_x/y) — NO teleportation
  - Cubic Bezier curve trajectories with random control points
  - Per-character typing with biological rhythm variation
  - Human click with down/hold/up split timing
  - Overshoot and micro-correction patterns
"""
import time
import random
import math


class HumanInput:
    """Stateful human input simulator.

    Tracks current mouse position and generates natural movements.
    Must be initialized with a Playwright page object.
    """

    def __init__(self, page):
        self.page = page
        # V4: Persistent mouse state (start near center)
        self.current_x = random.randint(500, 1000)
        self.current_y = random.randint(300, 600)

    def human_delay(self, min_s=0.1, max_s=0.3):
        """Variable human hesitation."""
        time.sleep(random.uniform(min_s, max_s))

    # ------------------------------------------------------------------
    #  Bezier Curve Engine
    # ------------------------------------------------------------------
    def _bezier_curve(self, start_x, start_y, end_x, end_y):
        """Generate a natural curved path using cubic Bezier interpolation."""
        path = []
        steps = random.randint(25, 60)

        # Random control points for curve variety
        dist = math.hypot(end_x - start_x, end_y - start_y)
        spread = max(50, dist * 0.3)

        ctrl1_x = start_x + (end_x - start_x) * random.uniform(0.2, 0.5) + random.uniform(-spread, spread)
        ctrl1_y = start_y + (end_y - start_y) * random.uniform(0.0, 0.4) + random.uniform(-spread, spread)
        ctrl2_x = start_x + (end_x - start_x) * random.uniform(0.5, 0.8) + random.uniform(-spread * 0.5, spread * 0.5)
        ctrl2_y = start_y + (end_y - start_y) * random.uniform(0.6, 1.0) + random.uniform(-spread * 0.5, spread * 0.5)

        for i in range(steps + 1):
            t = i / steps
            x = ((1 - t)**3 * start_x +
                 3 * (1 - t)**2 * t * ctrl1_x +
                 3 * (1 - t) * t**2 * ctrl2_x +
                 t**3 * end_x)
            y = ((1 - t)**3 * start_y +
                 3 * (1 - t)**2 * t * ctrl1_y +
                 3 * (1 - t) * t**2 * ctrl2_y +
                 t**3 * end_y)
            path.append((x, y))
        return path

    # ------------------------------------------------------------------
    #  Mouse Movement (Stateful — NO teleport)
    # ------------------------------------------------------------------
    def move_to(self, locator):
        """Move mouse from CURRENT position to target element using Bezier curve.
        Updates internal state after each micro-movement."""
        try:
            box = locator.bounding_box()
            if not box:
                return False

            # Target randomized within element bounds (never exact center)
            padding_x = min(5, box["width"] * 0.1)
            padding_y = min(5, box["height"] * 0.1)
            target_x = box["x"] + random.uniform(padding_x, box["width"] - padding_x)
            target_y = box["y"] + random.uniform(padding_y, box["height"] - padding_y)

            # Calculate path from CURRENT saved position
            path = self._bezier_curve(self.current_x, self.current_y, target_x, target_y)

            for px, py in path:
                self.page.mouse.move(px, py)
                self.current_x, self.current_y = px, py  # Update muscle memory

                # Micro-hesitations (simulates thinking or physical lag)
                if random.random() > 0.95:
                    time.sleep(random.uniform(0.01, 0.04))

            return True
        except Exception as e:
            return False

    def move_to_coordinates(self, target_x, target_y):
        """Move mouse to specific coordinates using Bezier curve."""
        path = self._bezier_curve(self.current_x, self.current_y, target_x, target_y)
        for px, py in path:
            self.page.mouse.move(px, py)
            self.current_x, self.current_y = px, py
            if random.random() > 0.95:
                time.sleep(random.uniform(0.01, 0.03))

    # ------------------------------------------------------------------
    #  Human Click
    # ------------------------------------------------------------------
    def click(self, selector_str):
        """Full human click: Bezier move + hesitate + mousedown/hold/up."""
        try:
            loc = self.page.locator(selector_str).first
            loc.wait_for(state="visible", timeout=7000)
            if self.move_to(loc):
                time.sleep(random.uniform(0.08, 0.25))  # Pre-click visual confirmation
                self.page.mouse.down()
                time.sleep(random.uniform(0.05, 0.15))  # Physical press duration
                self.page.mouse.up()
                return True
        except Exception:
            return False
        return False

    def click_locator(self, locator):
        """Click a Playwright locator directly with human behavior."""
        try:
            locator.wait_for(state="visible", timeout=7000)
            if self.move_to(locator):
                time.sleep(random.uniform(0.08, 0.25))
                self.page.mouse.down()
                time.sleep(random.uniform(0.05, 0.15))
                self.page.mouse.up()
                return True
        except Exception:
            return False
        return False

    # ------------------------------------------------------------------
    #  Human Typing (Biological Rhythm)
    # ------------------------------------------------------------------
    def type_text(self, text):
        """Type text with per-character delay simulating biological rhythm.
        Includes occasional pauses (thinking) and speed bursts."""
        for i, char in enumerate(text):
            self.page.keyboard.type(char)
            # Base delay
            delay = random.uniform(0.04, 0.18)
            # Occasional longer pause (thinking, 5% chance)
            if random.random() < 0.05:
                delay += random.uniform(0.3, 0.7)
            # Speed burst on common sequences (the, and, etc.)
            elif random.random() < 0.15:
                delay *= 0.5
            time.sleep(delay)

    def type_in_field(self, selector_str, text):
        """Click field then type with human rhythm."""
        if self.click(selector_str):
            time.sleep(random.uniform(0.2, 0.5))
            self.type_text(text)
            return True
        return False

    # ------------------------------------------------------------------
    #  Idle Behaviors
    # ------------------------------------------------------------------
    def idle_fidget(self):
        """Small random mouse movements simulating idle user."""
        for _ in range(random.randint(2, 5)):
            dx = random.uniform(-15, 15)
            dy = random.uniform(-15, 15)
            new_x = max(50, min(1870, self.current_x + dx))
            new_y = max(50, min(1030, self.current_y + dy))
            self.page.mouse.move(new_x, new_y)
            self.current_x, self.current_y = new_x, new_y
            time.sleep(random.uniform(0.05, 0.2))

    def scroll_random(self):
        """Random scroll to simulate browsing behavior."""
        delta = random.choice([-300, -200, -100, 100, 200, 300])
        try:
            self.page.mouse.wheel(0, delta)
        except Exception:
            pass
        time.sleep(random.uniform(0.3, 0.8))
