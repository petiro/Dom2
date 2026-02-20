import logging
import re

# 🔴 Pattern segreti (Telegram + API + Sessioni)
SENSITIVE_PATTERNS = [
    re.compile(r"[0-9]{8,10}:[a-zA-Z0-9_-]{35,}"),  # Bot token
    re.compile(r"1[a-zA-Z0-9\+\/]{40,}={0,2}"),     # StringSession
    re.compile(r"sk-[a-zA-Z0-9]{32,}"),             # API Key standard
    re.compile(r"sk-or-v1-[a-fA-F0-9]{64}"),        # API Key OpenRouter
    re.compile(r"[A-Za-z0-9]{45,}")                 # Fallback hash lunghi
]

def mask_sensitive(text):
    if not isinstance(text, str):
        return text
    for pattern in SENSITIVE_PATTERNS:
        text = pattern.sub("██SECRET_MASKED██", text)
    return text

class SecretFilter(logging.Filter):
    def filter(self, record):
        try:
            if isinstance(record.msg, str):
                record.msg = mask_sensitive(record.msg)

            if record.args:
                if isinstance(record.args, tuple):
                    record.args = tuple(mask_sensitive(str(a)) for a in record.args)
                elif isinstance(record.args, dict):
                    record.args = {k: mask_sensitive(str(v)) for k, v in record.args.items()}
        except Exception:
            pass
        return True
