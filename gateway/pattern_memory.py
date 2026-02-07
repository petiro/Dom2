import json, os, hashlib

# Resolve absolute base dir (works both in dev and inside PyInstaller exe)
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class PatternMemory:
    def __init__(self, storage_path=None):
        if storage_path is None:
            storage_path = os.path.join(_BASE_DIR, "data", "message_patterns.json")
        self.storage_path = storage_path
        self.patterns = self._load()

    def _load(self):
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, 'r') as f:
                    return json.load(f)
            except: return {}
        return {}

    def _save(self):
        os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
        with open(self.storage_path, 'w') as f:
            json.dump(self.patterns, f, indent=2)

    def get_pattern(self, text):
        # Crea una firma basata sulla struttura (emoji e parole chiave)
        signature = self._generate_signature(text)
        return self.patterns.get(signature)

    def save_pattern(self, text, result):
        signature = self._generate_signature(text)
        self.patterns[signature] = result
        self._save()

    def _generate_signature(self, text):
        # Estrae solo la struttura (emoji e placeholder) per identificare il formato
        import re
        # Rimuovi caratteri invisibili (zero-width spaces ecc.) e normalizza
        cleaned = text.replace("\u200b", "").replace("\u200c", "").replace("\u200d", "")
        cleaned = cleaned.replace("\xa0", " ").strip().lower()
        # Sostituisce nomi squadre e numeri con placeholder
        struct = re.sub(r'[a-zA-Z0-9]+', 'X', cleaned)
        # Normalizza spazi multipli
        struct = re.sub(r'\s+', ' ', struct).strip()
        return hashlib.md5(struct.encode()).hexdigest()
