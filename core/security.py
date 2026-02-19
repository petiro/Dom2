import os
import json
import logging
import hashlib
import base64
import platform
import uuid
import subprocess
from cryptography.fernet import Fernet, InvalidToken
from core.config_paths import VAULT_FILE

class Vault:
    def __init__(self):
        self.logger = logging.getLogger("Vault")
        self.key = self._generate_machine_key()
        self.cipher = Fernet(self.key)
        self.vault_path = VAULT_FILE

    def _generate_machine_key(self):
        if os.environ.get("GITHUB_ACTIONS") == "true":
            return base64.urlsafe_b64encode(hashlib.sha256(b"CI").digest()[:32])

        mid = "FALLBACK"
        try:
            if platform.system() == "Windows":
                mid = subprocess.check_output("wmic csproduct get uuid", shell=True).decode().split('\n')[1].strip()
            elif platform.system() == "Linux":
                with open("/etc/machine-id", encoding="utf-8") as f:
                    mid = f.read().strip()
            else:
                mid = str(uuid.getnode())
        except Exception:
            mid = platform.node()

        combined = f"{mid}|{os.getenv('USERNAME','')}"
        return base64.urlsafe_b64encode(hashlib.sha256(combined.encode()).digest()[:32])

    def decrypt_data(self):
        try:
            if not os.path.exists(self.vault_path):
                return {}
            with open(self.vault_path, "rb") as f:
                return json.loads(self.cipher.decrypt(f.read()).decode())
        except InvalidToken:
            self.logger.error("Vault decrypt failed: Invalid Token")
            return {}
        except Exception as e:
            self.logger.error("Vault error: %s", e)
            return {}

    def encrypt_data(self, data):
        try:
            os.makedirs(os.path.dirname(self.vault_path), exist_ok=True)
            with open(self.vault_path, "wb") as f:
                f.write(self.cipher.encrypt(json.dumps(data).encode()))
            return True
        except Exception:
            return False