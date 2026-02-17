def _on_mapping_done(self, found_elements):
        self.log_message.emit(f"✅ Scansione completata. Trovati {len(found_elements)} elementi candidati.")
        
        # Qui simuliamo l'intelligenza che mappa i candidati ai campi richiesti
        # In un sistema V8 questo lo farebbe l'AI Parser inviando la lista a GPT/Claude
        
        self.log_message.emit("🧠 Tentativo di identificazione selettori (Heuristic)...")
        
        new_selectors = {}
        
        # Logica euristica semplice per "indovinare" i campi (può essere migliorata con AI)
        for el in found_elements:
            txt = el.lower()
            
            # Indovina Input Importo
            if "input" in txt and ("stake" in txt or "amount" in txt or "importo" in txt):
                new_selectors["stake_input"] = self._extract_css(el)
            
            # Indovina Bottone Scommetti
            elif "button" in txt and ("scommetti" in txt or "place" in txt or "bet" in txt):
                new_selectors["place_button"] = self._extract_css(el)
                
            # Indovina Login
            elif "button" in txt and ("accedi" in txt or "login" in txt):
                new_selectors["login_button"] = self._extract_css(el)

        # Salva o notifica
        if new_selectors:
            import yaml
            import os
            from core.config_paths import CONFIG_DIR
            
            path = os.path.join(CONFIG_DIR, "selectors_discovered.yaml")
            with open(path, "w") as f:
                yaml.dump(new_selectors, f)
            
            self.log_message.emit(f"💾 Selettori salvati in: {path}")
            self.log_message.emit("⚠️ Controlla il file e rinominalo in selectors.yaml se corretto!")
        else:
            self.log_message.emit("❌ Nessun selettore chiave identificato automaticamente.")

    def _extract_css(self, element_string):
        # Helper per estrarre una classe o ID dalla stringa grezza dello scanner
        # Esempio input: "Tag: Scommetti | Class: btn-place" -> ".btn-place"
        try:
            parts = element_string.split("| Class:")
            if len(parts) > 1:
                cls = parts[1].strip()
                if cls: return f".{cls.split()[0]}" # Prende la prima classe
        except: pass
        return "SELETTORE_NON_TROVATO"