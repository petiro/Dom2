import time
import math
import random
import logging
from datetime import datetime
from core.geometry import cubic_bezier  # Importa la logica condivisa

class HumanMouse:
    def __init__(self, page, logger=None):
        self.page = page
        self.logger = logger or logging.getLogger(self.__class__.__name__)
        self.start_session_time = datetime.now()
        self.overshoot_probability = 0.30
        self.fatigue_multiplier = 1.0

        # Recupera dimensioni viewport per Bounds Checking (Fix Medium #7)
        try:
            viewport = page.viewport_size
            self.max_w = viewport['width'] if viewport else 1920
            self.max_h = viewport['height'] if viewport else 1080
        except:
            self.max_w = 1920
            self.max_h = 1080

    def _calculate_fatigue(self):
        elapsed_mins = (datetime.now() - self.start_session_time).total_seconds() / 60
        self.fatigue_multiplier = 1 + (elapsed_mins * 0.003)

    def _ease_out_quart(self, x):
        return 1 - pow(1 - x, 4)

    def move_to(self, target_x, target_y, steps=None):
        # Bounds Checking: Assicura che il mouse non esca dall'area visibile
        target_x = max(0, min(target_x, self.max_w))
        target_y = max(0, min(target_y, self.max_h))

        self._calculate_fatigue()

        # Start casuale (simulato)
        start_x = random.randint(100, 800)
        start_y = random.randint(100, 600)

        dist = math.hypot(target_x - start_x, target_y - start_y)

        # Overshoot Logic
        do_overshoot = random.random() < self.overshoot_probability
        virtual_x, virtual_y = target_x, target_y

        if do_overshoot:
            overshoot_amt = random.randint(10, 40)
            angle = math.atan2(target_y - start_y, target_x - start_x)
            virtual_x = target_x + math.cos(angle) * overshoot_amt
            virtual_y = target_y + math.sin(angle) * overshoot_amt

        # Control Points
        c1_x = start_x + (virtual_x - start_x) * random.uniform(0.2, 0.5) + random.randint(-50, 50)
        c1_y = start_y + (virtual_y - start_y) * random.uniform(0.2, 0.5) + random.randint(-50, 50)
        c2_x = start_x + (virtual_x - start_x) * random.uniform(0.6, 0.9) + random.randint(-50, 50)
        c2_y = start_y + (virtual_y - start_y) * random.uniform(0.6, 0.9) + random.randint(-50, 50)

        base_duration = (dist / 1000) * random.uniform(0.8, 1.2) * self.fatigue_multiplier
        base_duration = max(0.4, min(base_duration, 1.8))

        if steps is None: steps = int(base_duration * 60)

        for i in range(steps):
            t = i / steps
            ease_t = self._ease_out_quart(t)

            # Usa la funzione importata da geometry.py (Fix DRY)
            x, y = cubic_bezier((start_x, start_y), (c1_x, c1_y), (c2_x, c2_y), (virtual_x, virtual_y), ease_t)

            jitter = random.uniform(-1.5, 1.5) * self.fatigue_multiplier
            try: self.page.mouse.move(x + jitter, y + jitter)
            except: pass
            time.sleep(base_duration / steps)

        if do_overshoot:
            time.sleep(random.uniform(0.05, 0.1))
            self.page.mouse.move(target_x, target_y, steps=5)

    def click_locator(self, locator):
        """Metodo pubblico per cliccare un Playwright Locator."""
        try:
            box = locator.bounding_box()
            if not box: return False

            safe_w, safe_h = box["width"] * 0.6, box["height"] * 0.6
            tx = box["x"] + box["width"]/2 + random.uniform(-safe_w/2, safe_w/2)
            ty = box["y"] + box["height"]/2 + random.uniform(-safe_h/2, safe_h/2)

            self.move_to(tx, ty)
            time.sleep(random.uniform(0.05, 0.2))
            self.page.mouse.down()
            time.sleep(random.uniform(0.06, 0.12))
            self.page.mouse.up()
            return True
        except: return False

    def click_element(self, selector):
        """Legacy wrapper per string selector."""
        try:
            loc = self.page.locator(selector).first
            loc.wait_for(state="visible", timeout=3000)
            return self.click_locator(loc)
        except: return False

    def idle_behavior(self):
        if random.random() < 0.3:
            try: self.page.mouse.move(random.randint(200, 600), random.randint(200, 600), steps=15)
            except: pass
