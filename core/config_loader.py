import os
import json
import logging
import yaml

def get_project_root():
    import sys
    if getattr(sys, 'frozen', False): return os.path.dirname(sys.executable)
    try: return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    except: return os.getcwd()

def load_secrets():
    """Carica le chiavi sensibili dal file secrets.json locale."""
    root = get_project_root()
    secrets_path = os.path.join(root, "config", "secrets.json")
    
    # Se il file non esiste, ritorna vuoto (l'utente deve salvarle dalla UI)
    if not os.path.exists(secrets_path):
        return {}

    try:
        with open(secrets_path, "r") as f:
            data = json.load(f)
            return {k: str(v).strip() for k, v in data.items()}
    except Exception as e:
        print(f"❌ Errore lettura secrets.json: {e}")
        return {}

def load_secure_config(path="config/config.yaml"):
    """unisce config base e secrets"""
    # 1. Carica secrets
    secrets = load_secrets()
    
    # 2. Carica config base (se esiste)
    config = {}
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f) or {}
        except: pass
    
    # 3. Merge: i secrets vincono sempre
    config.update(secrets)
    return config
