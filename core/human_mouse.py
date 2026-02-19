"""
Modulo HumanMouse.
Fornisce interazioni del mouse simili a quelle umane per Playwright,
implementando jitter e delay randomici per evitare il rilevamento dei bot.
"""

import random
import time
import logging
from typing import Any, Optional


class HumanMouse:
    """
    Simula movimenti e click del mouse simili a quelli umani.
    Integrazione CI-safe, pylint-safe e thread-safe per Playwright.
    """

    def __init__(self, page: Any, logger: Optional[logging.Logger] = None) -> None:
        self.page = page
        self.logger = logger or logging.getLogger("HumanMouse")

    def click(self, locator: Any) -> None:
        """
        Esegue un click "umano" sul locator fornito.
        """
        self._move_like_human(locator)
        self._perform_click(locator)

    def _move_like_human(self, locator: Any) -> None:
        """
        Simula micro-movimenti del mouse verso il target.
        """
        try:
            box = locator.bounding_box()
            if not box:
                return

            target_x = box["x"] + box["width"] / 2.0
            target_y = box["y"] + box["height"] / 2.0

            jitter_x = random.uniform(-3.0, 3.0)
            jitter_y = random.uniform(-3.0, 3.0)

            self.page.mouse.move(target_x + jitter_x, target_y + jitter_y, steps=8)
            time.sleep(random.uniform(0.05, 0.15))

        except Exception as e:  # pylint: disable=broad-exception-caught
            self.logger.debug("HumanMouse move fallback attivato: %s", e)

    # 🔴 FIX 2: CLICK NATIVO MOUSE (NO locator.click)
    def _perform_click(self, locator: Any) -> bool:
        """
        Esegue il click fisico nativo abbassando e alzando il mouse.
        """
        try:
            box = locator.bounding_box()
            if not box:
                self.logger.error("Bounding box non trovata per click")
                return False

            x = box["x"] + box["width"]/2 + random.uniform(-3,3)
            y = box["y"] + box["height"]/2 + random.uniform(-3,3)

            # movimento umano verso l'esatto punto
            self.page.mouse.move(x, y, steps=random.randint(8,16))

            time.sleep(random.uniform(0.05,0.15))

            # 🔴 CLICK NATIVO HARDWARE-LEVEL
            self.page.mouse.down()
            time.sleep(random.uniform(0.08,0.18))
            self.page.mouse.up()

            return True
            
        except Exception as e:  # pylint: disable=broad-exception-caught
            self.logger.debug("HumanMouse native click fallback attivato: %s", e)
            return False