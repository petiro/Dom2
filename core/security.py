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
        self.logger = logging.getLogger(self.__class__.__name__)
        self.key = self._generate_machine_key()
        self.cipher = Fernet(self.key)
        self.vault_path = VAULT_FILE

    def _generate_machine_key(self):
        """Generate a stable key based on hardware UUID."""
        if os.environ.get("GITHUB_ACTIONS") == "true":
            serial = os.getenv("CI_RUN_ID") or uuid.uuid4().hex
            hash_key = hashlib.sha256(serial.encode()).digest()
            return base64.urlsafe_b64encode(hash_key[:32])

        machine_id = "FALLBACK_ID"

        try:
            if platform.system() == "Windows":
                raw = subprocess.check_output(
                    ["wmic", "csproduct", "get", "uuid"],
                    stderr=subprocess.DEVNULL
                ).decode()
                lines = raw.strip().split('\n')
                machine_id = lines[1].strip() if len(lines) > 1 else machine_id

            elif platform.system() == "Linux":
                if os.path.exists("/etc/machine-id"):
                    with open("/etc/machine-id") as f:
                        machine_id = f.read().strip()
                elif os.path.exists("/var/lib/dbus/machine-id"):
                    with open("/var/lib/dbus/machine-id") as f:
                        machine_id = f.read().strip()

            elif platform.system() == "Darwin":
                raw = subprocess.check_output(
                    ["ioreg", "-rd1", "-c", "IOPlatformExpertDevice"],
                    stderr=subprocess.DEVNULL
                ).decode()
                for line in raw.split('\n'):
                    if "IOPlatformUUID" in line:
                        parts = line.split('"')
                        machine_id = parts[-2] if len(parts) >= 2 else machine_id
                        break

        except Exception as e:
            self.logger.warning(f"Fallback key generation: {e}")
            machine_id = platform.node() or "GENERIC_HOST"

        username = os.getenv("USERNAME", os.getenv("USER", "user"))
        combined = f"{machine_id}|{username}"

        hash_key = hashlib.sha256(combined.encode()).digest()
        return base64.urlsafe_b64encode(hash_key[:32])

    def encrypt_data(self, data_dict):
        try:
            json_data = json.dumps(data_dict).encode()
            encrypted_data = self.cipher.encrypt(json_data)
            os.makedirs(os.path.dirname(self.vault_path), exist_ok=True)
            with open(self.vault_path, "wb") as f:
                f.write(encrypted_data)
            return True
        except Exception as e:
            self.logger.error(f"Encrypt failed: {e}")
            return False

    def decrypt_data(self):
        """Robust error handling for vault decryption."""
        try:
            if not os.path.exists(self.vault_path):
                return {}

            with open(self.vault_path, "rb") as f:
                encrypted_data = f.read()

            decrypted_data = self.cipher.decrypt(encrypted_data)
            return json.loads(decrypted_data.decode())

        except json.JSONDecodeError:
            self.logger.error("Vault corrupted: invalid JSON.", exc_info=True)
            return {}
        except InvalidToken:
            self.logger.error("Vault decryption failed: invalid token or machine change.", exc_info=True)
            return {}
        except Exception as e:
            self.logger.error(f"Unexpected Vault error: {e}", exc_info=True)
            return {}
