import os
import json
import logging
import hashlib
import base64
import platform
import uuid
from cryptography.fernet import Fernet, InvalidToken
from core.config_paths import VAULT_FILE # Import centralizzato

class Vault:
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.key = self._generate_machine_key()
        self.cipher = Fernet(self.key)
        self.vault_path = VAULT_FILE

    def _generate_machine_key(self):
        """Genera una chiave univoca. Fix Low #15: Random in CI."""
        if os.environ.get("GITHUB_ACTIONS") == "true":
            # In CI usiamo una chiave randomica per evitare che sia predicibile
            serial = os.getenv("CI_RUN_ID") or uuid.uuid4().hex
            hash_key = hashlib.sha256(serial.encode()).digest()
            return base64.urlsafe_b64encode(hash_key[:32])

        identifiers = [platform.node() or ""]
        identifiers.append(platform.machine() or "")
        identifiers.append(os.getenv("USERNAME", os.getenv("USER", "")))

        combined = "|".join(identifiers) or "FALLBACK_ID"
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
        """Fix High #2: Gestione robusta errori."""
        try:
            if not os.path.exists(self.vault_path):
                return {}

            with open(self.vault_path, "rb") as f:
                encrypted_data = f.read()

            decrypted_data = self.cipher.decrypt(encrypted_data)
            return json.loads(decrypted_data.decode())

        except FileNotFoundError:
            return {}
        except json.JSONDecodeError:
            self.logger.error("Vault corrotto: JSON invalido.", exc_info=True)
            return {}
        except InvalidToken:
            self.logger.error("Vault decrittazione fallita: Token invalido o cambio macchina.", exc_info=True)
            return {}
        except Exception as e:
            self.logger.error(f"Errore Vault inatteso: {e}", exc_info=True)
            return {}
