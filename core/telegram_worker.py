# In main.py, modifica la parte finale così:

    # ... codice precedente ...

    # Inizializza variabili vuote per evitare crash se i moduli mancano
    vision = None 
    telegram_learner = None
    rpa_healer = None

    # Tenta di caricare i moduli opzionali
    if config.get("learning", {}).get("enabled", True):
        try:
            # from ai.rpa_healer import RPAHealer  <-- Commentato perché manca il file
            # rpa_healer = RPAHealer(...)
            pass 
        except Exception as e:
            logger.error(f"Failed to initialize AI: {e}")

    logger.info("Starting desktop application...")
    # Passa le variabili (che ora sono None se il caricamento fallisce)
    sys.exit(run_app(vision, telegram_learner, rpa_healer, logger))