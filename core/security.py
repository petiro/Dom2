import os
import json
import subprocess
import hashlib
import base64
import platform
from cryptography.fernet import Fernet
from core.utils import get_project_root


class Vault:
    def __init__(self):
        self.key = self._generate_machine_key()
        self.cipher = Fernet(self.key)
        self.vault_path = os.path.join(get_project_root(), "config", "vault.bin")

    def _generate_machine_key(self):
        """Genera una chiave univoca basata sull'hardware della macchina."""
        if os.environ.get("GITHUB_ACTIONS") == "true":
            serial = "CI_TEST_ID"
        elif platform.system().lower() == "windows":
            try:
                result = subprocess.run(
                    ["wmic", "csproduct", "get", "uuid"],
                    check=True, stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL, text=True
                )
                output = result.stdout.splitlines()
                serial = output[1].strip() if len(output) > 1 else "DEFAULT_MACHINE_FALLBACK"
            except (OSError, subprocess.CalledProcessError):
                serial = platform.node() or "FALLBACK_ID"
        else:
            serial = platform.node() or "FALLBACK_ID"

        hash_key = hashlib.sha256(serial.encode()).digest()
        return base64.urlsafe_b64encode(hash_key[:32])

    def encrypt_data(self, data_dict):
        """Cripta un dizionario e lo salva su vault.bin."""
        try:
            json_data = json.dumps(data_dict).encode()
            encrypted_data = self.cipher.encrypt(json_data)
            os.makedirs(os.path.dirname(self.vault_path), exist_ok=True)
            with open(self.vault_path, "wb") as f:
                f.write(encrypted_data)
            return True
        except Exception:
            return False

    def decrypt_data(self):
        """Decripta vault.bin e ritorna il dizionario."""
        if not os.path.exists(self.vault_path):
            return {}
        try:
            with open(self.vault_path, "rb") as f:
                encrypted_data = f.read()
            decrypted_data = self.cipher.decrypt(encrypted_data)
            return json.loads(decrypted_data.decode())
        except Exception:
            return {}
