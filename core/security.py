import os
import json
import subprocess
import hashlib
import base64
from cryptography.fernet import Fernet

class Vault:
    def __init__(self):
        self.key = self._generate_machine_key()
        self.cipher = Fernet(self.key)
        self.vault_path = "config/vault.bin"

    def _generate_machine_key(self):
        if os.environ.get("CI_MODE") == "1":
            serial = "GITHUB_ACTIONS_TEST_ID"
        else:
            try:
                # Comando Windows per ID Scheda Madre
                cmd = 'wmic baseboard get serialnumber'
                output = subprocess.check_output(cmd, shell=True).decode().splitlines()
                # Prende la seconda riga o usa un fallback se fallisce
                serial = output[1].strip() if len(output) > 1 else "DEFAULT_MACHINE_FALLBACK"
            except Exception:
                # Fallback universale se WMIC fallisce (Windows 11/Server 2022)
                serial = os.environ.get('COMPUTERNAME', 'UNKNOWN_HOST')
            
        # Crea chiave a 32 byte
        hash_key = hashlib.sha256(serial.encode()).digest()
        return base64.urlsafe_b64encode(hash_key[:32])

    def encrypt_data(self, data_dict):
        json_data = json.dumps(data_dict).encode()
        encrypted_data = self.cipher.encrypt(json_data)
        os.makedirs("config", exist_ok=True)
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
