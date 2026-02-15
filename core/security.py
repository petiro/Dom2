import os
import json
import logging
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
        """Genera una chiave univoca basata su multipli identificatori della macchina."""
        if os.environ.get("GITHUB_ACTIONS") == "true":
            serial = "CI_TEST_ID"
            hash_key = hashlib.sha256(serial.encode()).digest()
            return base64.urlsafe_b64encode(hash_key[:32])

        # Raccoglie piu identificatori per una chiave piu resistente
        identifiers = []

        # 1. Hostname
        identifiers.append(platform.node() or "")

        # 2. UUID macchina (Windows) o machine-id (Linux)
        if platform.system().lower() == "windows":
            try:
                result = subprocess.run(
                    ["wmic", "csproduct", "get", "uuid"],
                    check=True, stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL, text=True
                )
                output = result.stdout.splitlines()
                if len(output) > 1 and output[1].strip():
                    identifiers.append(output[1].strip())
            except (OSError, subprocess.CalledProcessError):
                pass
        else:
            # Linux/Mac: /etc/machine-id o /var/lib/dbus/machine-id
            for mid_path in ["/etc/machine-id", "/var/lib/dbus/machine-id"]:
                try:
                    with open(mid_path, "r") as f:
                        mid = f.read().strip()
                        if mid:
                            identifiers.append(mid)
                            break
                except (FileNotFoundError, PermissionError):
                    pass

        # 3. Username come sale aggiuntivo
        identifiers.append(os.getenv("USERNAME", os.getenv("USER", "")))

        # 4. Combina tutti gli identificatori
        combined = "|".join(identifiers)
        if not combined.replace("|", ""):
            combined = "FALLBACK_MACHINE_ID"

        hash_key = hashlib.sha256(combined.encode()).digest()
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
        except Exception as e:
            logging.getLogger("SuperAgent").error(f"Failed to encrypt data for vault: {e}")
            return False

    def decrypt_data(self):
        """Decripta vault.bin e ritorna il dizionario. Raises on error."""
        with open(self.vault_path, "rb") as f:
            encrypted_data = f.read()
        decrypted_data = self.cipher.decrypt(encrypted_data)
        return json.loads(decrypted_data.decode())
