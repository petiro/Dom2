import os
from pathlib import Path
from cryptography.fernet import Fernet

KEY_FILE = os.path.join(str(Path.home()), ".superagent_data", ".master.key")

class CryptoVault:
    @classmethod
    def _get_key(cls):
        if not os.path.exists(KEY_FILE):
            key = Fernet.generate_key()
            os.makedirs(os.path.dirname(KEY_FILE), exist_ok=True)
            with open(KEY_FILE, "wb") as f: 
                f.write(key)
        with open(KEY_FILE, "rb") as f: 
            return f.read()

    @classmethod
    def encrypt(cls, text):
        if not text: return ""
        f = Fernet(cls._get_key())
        return f.encrypt(text.encode()).decode()

    @classmethod
    def decrypt(cls, cipher_text):
        if not cipher_text: return ""
        try:
            f = Fernet(cls._get_key())
            return f.decrypt(cipher_text.encode()).decode()
        except Exception:
            return ""
