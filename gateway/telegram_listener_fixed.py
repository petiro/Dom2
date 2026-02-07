import os
import yaml


def validate_telegram_config():
    """
    Validate Telegram credentials at startup.
    The actual connection is handled via the UI TelegramTab connect button.
    Returns (api_id, api_hash) tuple if valid, raises RuntimeError otherwise.
    """
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_path = os.path.join(base_dir, "config", "config.yaml")

    if not os.path.exists(config_path):
        raise RuntimeError("config.yaml non trovato")

    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}

    telegram_cfg = config.get("telegram", {})
    api_id = telegram_cfg.get("api_id")
    api_hash = telegram_cfg.get("api_hash")

    if not api_id or not api_hash:
        raise RuntimeError("Telegram api_id/api_hash non configurati in config.yaml - configura dal tab Telegram nella UI")

    print(f"Telegram config valida (api_id={api_id})")
    return api_id, api_hash


# Keep backward compatibility alias
start_telegram_listener = validate_telegram_config
