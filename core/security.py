import os
import json
import subprocess
import hashlib
import base64
import platform
from cryptography.fernet import Fernet

_ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

class Vault:
    def __init__(self):
        self.key = self._generate_machine_key()
        self.cipher = Fernet(self.key)
        self.vault_path = os.path.join(_ROOT_DIR, "config", "vault.bin")

    def _generate_machine_key(self):
        if os.environ.get("GITHUB_ACTIONS") == "true":
            serial = "CI_TEST_ID"
        else:
            try:
                cmd = 'wmic csproduct get uuid'
                output = subprocess.check_output(cmd, shell=True, stderr=subprocess.DEVNULL).decode().split('\n')
                serial = output[1].strip() if len(output) > 1 else "DEFAULT_MACHINE_FALLBACK"
            except Exception:
                serial = platform.node() or "FALLBACK_ID"
            
        # Crea chiave a 32 byte
        hash_key = hashlib.sha256(serial.encode()).digest()
        return base64.urlsafe_b64encode(hash_key[:32])

    def encrypt_data(self, data_dict):
        json_data = json.dumps(data_dict).encode()
        encrypted_data = self.cipher.encrypt(json_data)
        os.makedirs(os.path.dirname(self.vault_path), exist_ok=True)
        with open(self.vault_path, "wb") as f:
            f.write(encrypted_data)

    def decrypt_data(self):
        if not os.path.exists(self.vault_path):
            return {}
        try:
            with open(self.vault_path, "rb") as f:
                encrypted_data = f.read()
            decrypted_data = self.cipher.decrypt(encrypted_data)
            return json.loads(decrypted_data.decode())
        except Exception:
            return {}
