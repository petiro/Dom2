def find_odds(self, match, market):
        """
        Cerca la quota reale nella pagina corrente.
        Richiede che il selettore 'odds_value' sia definito in selectors.yaml.
        """
        if not self.launch_browser(): return 0.0
        selectors = self._load_selectors()
        
        # Recupera il selettore generico per la quota
        # Esempio YAML: odds_value: ".market-outcome .odds"
        odds_sel = selectors.get("odds_value")
        
        if not odds_sel:
            self.logger.error("❌ Manca 'odds_value' in selectors.yaml")
            return 0.0

        try:
            # Tenta di trovare l'elemento (attesa dinamica)
            loc = self.page.locator(odds_sel).first
            loc.wait_for(state="visible", timeout=3000)
            
            # Estrae il testo e pulisce (es: "1,50" -> 1.50)
            text = loc.text_content().strip()
            text = text.replace(",", ".")
            
            odds = float(text)
            self.logger.info(f"📊 Quota trovata: {odds}")
            return odds
        except Exception as e:
            self.logger.warning(f"⚠️ Impossibile leggere quota: {e}")
            return 0.0

    def scan_page_elements(self, url):
        """
        Scansiona la pagina per trovare potenziali selettori (utile per debug).
        """
        if not self.launch_browser(): return []
        
        found_elements = []
        try:
            # Cerca input, bottoni e span con classi significative
            elements = self.page.locator("button, input[type='text'], .price, .odds").all()
            for el in elements[:20]: # Limitiamo a 20 per velocità
                try:
                    txt = el.text_content().strip()[:20]
                    cls = el.get_attribute("class") or ""
                    if txt or cls:
                        found_elements.append(f"Tag: {txt} | Class: {cls}")
                except: pass
        except Exception as e:
            self.logger.error(f"Scan error: {e}")
            
        return found_elements