import time
import math
import random
import logging
from datetime import datetime
from core.geometry import cubic_bezier, clamp_point

class HumanMouse:
    def __init__(self, page, logger=None):
        self.page = page
        self.logger = logger or logging.getLogger(self.__class__.__name__)
        self.start_session_time = datetime.now()
        self.overshoot_probability = 0.30
        self.fatigue_multiplier = 1.0
        
        try:
            viewport = page.viewport_size
            self.max_w = viewport['width'] if viewport else 1920
            self.max_h = viewport['height'] if viewport else 1080
        except:
            self.max_w = 1920
            self.max_h = 1080

        self.current_x = random.randint(int(self.max_w * 0.4), int(self.max_w * 0.6))
        self.current_y = random.randint(int(self.max_h * 0.4), int(self.max_h * 0.6))

    def _calculate_fatigue(self):
        elapsed = (datetime.now() - self.start_session_time).total_seconds() / 60
        self.fatigue_multiplier = 1 + (elapsed * 0.003)

    def _ease_out_quart(self, x):
        return 1 - pow(1 - x, 4)

    def move_to(self, target_x, target_y, steps=None):
        target_x, target_y = clamp_point(target_x, target_y, self.max_w, self.max_h)
        self._calculate_fatigue()
        
        start_x, start_y = self.current_x, self.current_y
        dist = math.hypot(target_x - start_x, target_y - start_y)
        
        do_overshoot = random.random() < self.overshoot_probability
        virtual_x, virtual_y = target_x, target_y
        
        if do_overshoot:
            over = random.randint(10, 40)
            angle = math.atan2(target_y - start_y, target_x - start_x)
            virtual_x += math.cos(angle) * over
            virtual_y += math.sin(angle) * over

        c1_x = start_x + (virtual_x - start_x) * random.uniform(0.2, 0.5)
        c1_y = start_y + (virtual_y - start_y) * random.uniform(0.2, 0.5)
        c2_x = start_x + (virtual_x - start_x) * random.uniform(0.6, 0.9)
        c2_y = start_y + (virtual_y - start_y) * random.uniform(0.6, 0.9)

        base_dur = max(0.4, min((dist / 1000) * self.fatigue_multiplier, 1.8))
        if steps is None: steps = int(base_dur * 60)

        for i in range(steps):
            t = i / steps
            x, y = cubic_bezier((start_x, start_y), (c1_x, c1_y), (c2_x, c2_y), (virtual_x, virtual_y), self._ease_out_quart(t))
            try:
                cx, cy = clamp_point(x, y, self.max_w, self.max_h)
                self.page.mouse.move(cx, cy)
                self.current_x, self.current_y = cx, cy
            except: pass
            time.sleep(base_dur / steps)

        if do_overshoot:
            self.page.mouse.move(target_x, target_y, steps=5)
            self.current_x, self.current_y = target_x, target_y

    def click_locator(self, locator):
        max_retries = 2
        for attempt in range(max_retries):
            try:
                box = locator.bounding_box()
                if not box:
                    if attempt < max_retries - 1:
                        time.sleep(0.5)
                        continue
                    return False
                
                safe_w, safe_h = box["width"] * 0.6, box["height"] * 0.6
                tx = box["x"] + box["width"]/2 + random.uniform(-safe_w/2, safe_w/2)
                ty = box["y"] + box["height"]/2 + random.uniform(-safe_h/2, safe_h/2)
                
                self.move_to(tx, ty)
                time.sleep(random.uniform(0.05, 0.2))
                self.page.mouse.down()
                time.sleep(random.uniform(0.06, 0.12))
                self.page.mouse.up()
                return True
            except Exception as e:
                self.logger.warning(f"Human click attempt {attempt+1} failed: {e}")
                time.sleep(0.5)
        
        try:
            self.logger.info("Human click failed, forcing standard click.")
            locator.click(force=True)
            return True
        except: return False

    def idle_behavior(self):
        if random.random() < 0.3:
            try: 
                offset_x = random.randint(-50, 50)
                offset_y = random.randint(-50, 50)
                self.move_to(self.current_x + offset_x, self.current_y + offset_y)
            except: pass