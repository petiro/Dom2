import yaml
import os

def load_secure_config(path="config/config.yaml"):
    """
    Carica la configurazione da file YAML e maschera i dati sensibili
    per evitare che appaiano nei log se la config viene stampata.
    I dati reali verranno sovrascritti dal Vault nel Controller.
    """
    if not os.path.exists(path):
        return {}

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        # Mascheramento preventivo (Security through Obscurity per i log)
        if "api_key" in data:
            data["api_key"] = "****************"
            
        if "telegram" in data:
            if "api_id" in data["telegram"]:
                data["telegram"]["api_id"] = "000000"
            if "api_hash" in data["telegram"]:
                data["telegram"]["api_hash"] = "****************"
        
        if "pin" in data:
            data["pin"] = "****"
            
        return data
    except Exception as e:
        print(f"Errore caricamento config base: {e}")
        return {}
