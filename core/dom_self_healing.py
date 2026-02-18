import yaml
import os
import logging
from core.config_paths import CONFIG_DIR
# Import dinamico all'interno del metodo per evitare cicli se necessario, 
# ma qui lo mettiamo safe a livello modulo se controller gestisce bene i path.

class DOMSelfHealing:
    def __init__(self, executor):
        self.executor = executor
        self.logger = logging.getLogger("SelfHealing")

    def heal(self, key):
        self.logger.warning(f"♻️ AVVIO SELF-HEALING per: {key}")
        
        try:
            # Import locale per evitare import loop con controller/worker
            from core.auto_mapper_worker import AutoMapperWorker
            
            url = self.executor.page.url
            # Esecuzione sincrona rapida (simulata riutilizzando la logica interna)
            mapper = AutoMapperWorker(self.executor, url)
            
            # Hack: Chiamiamo i metodi interni per fare scansione immediata senza thread signal loop
            page = self.executor.page
            cdp = page.context.new_cdp_session(page)
            cdp.send("DOM.enable")
            resp = cdp.send("DOM.getFlattenedDocument", {"depth": -1, "pierce": True})
            
            nodes = resp.get("nodes", [])
            elements = mapper._extract(nodes)
            selectors = mapper._ai_match(elements)
            
            # Aggiorna YAML se troviamo qualcosa
            if selectors:
                mapper._save(selectors)
                
            new_sel = selectors.get(key)
            if new_sel:
                self.logger.info(f"✅ HEALED: {key} -> {new_sel}")
                return new_sel
                
        except Exception as e:
            self.logger.error(f"Heal error: {e}")
            
        return None
