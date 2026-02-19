"""
Modulo HumanMouse.
Fornisce interazioni del mouse simili a quelle umane per Playwright.
"""

import random
import time
import logging
from typing import Any, Optional


class HumanMouse:
    """
    Simula movimenti e click del mouse simili a quelli umani.
    """

    def __init__(self, page: Any, logger: Optional[logging.Logger] = None) -> None:
        self.page = page
        self.logger = logger or logging.getLogger("HumanMouse")

    # 🔴 ECCO IL METODO CHE PYLINT CERCAVA E NON TROVAVA SU GITHUB
    def click(self, locator: Any) -> None:
        """
        Esegue un click "umano" sul locator fornito.
        """
        self._move_like_human(locator)
        self._perform_click(locator)

    def _move_like_human(self, locator: Any) -> None:
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
            self.logger.debug("HumanMouse move fallback: %s", e)

    def _perform_click(self, locator: Any) -> None:
        try:
            locator.click(delay=random.randint(80, 180))
        except Exception as e:  # pylint: disable=broad-exception-caught
            self.logger.debug("HumanMouse click fallback: %s", e)
            locator.click()
