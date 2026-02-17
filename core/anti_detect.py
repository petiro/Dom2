STEALTH_INJECTION_V4 = "// Stealth script..."

class AntiDetect:
    def __init__(self, page):
        self.page = page
        self._stealth_applied = False

    def apply(self):
        if self._stealth_applied: return
        try:
            self.page.add_init_script(STEALTH_INJECTION_V4)
            self._stealth_applied = True
        except: pass