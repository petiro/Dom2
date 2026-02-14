import re
import logging

# Regex whitelist espansa per sintassi Playwright avanzata
# Ammette: Alfanumerici, spazi, underscore, trattini, punti, hash
# Sintassi Playwright: >>, =, :, (), [], "", '', @, *
SAFE_SELECTOR = re.compile(r"^[a-zA-Z0-9\.\#\-\_\[\]\=\s\:\(\)\"\'>@\*]+$")

def validate_selector(selector: str) -> bool:
    """
    Valida un selettore Playwright/CSS.
    Blocca injection (javascript:) e lunghezza eccessiva, ma permette sintassi Playwright.
    """
    if not selector:
        return False
    
    # 1. Check Lunghezza (Anti-DoS)
    if len(selector) > 300: 
        return False
    
    # 2. Check Injection esplicita
    if "javascript:" in selector.lower() or "vbscript:" in selector.lower():
        return False
    
    # 3. Check Whitelist caratteri
    if not SAFE_SELECTOR.match(selector):
        return False
        
    return True
