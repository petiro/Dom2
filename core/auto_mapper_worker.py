import time
import re
import yaml
import os
from PySide6.QtCore import QObject, Signal
from core.config_paths import CONFIG_DIR

# Nessun import di classi Core qui (es. DomExecutor)
# Riceve 'executor' come oggetto generico nel costruttore

class AutoMapperWorker(QObject):
    finished = Signal(dict)
    log = Signal(str)

    def __init__(self, executor, url):
        super().__init__()
        self.executor = executor
        self.url = url

    def run(self):
        cdp = None
        try:
            self.log.emit(f"🚀 AI Auto-Mapping: {self.url}")

            # Usiamo getattr per evitare import diretti di tipo
            launch_method = getattr(self.executor, "launch_browser", None)
            if launch_method and not launch_method():
                self.log.emit("❌ Browser fail")
                self.finished.emit({})
                return

            page = getattr(self.executor, "page", None)
            if not page:
                self.log.emit("❌ No active page")
                self.finished.emit({})
                return

            try:
                page.goto(self.url, timeout=60000)
                page.wait_for_load_state("domcontentloaded")
            except: pass

            self._auto_scroll(page)

            cdp = page.context.new_cdp_session(page)
            cdp.send("DOM.enable")

            start_scan = time.time()
            resp = cdp.send("DOM.getFlattenedDocument", {"depth": -1, "pierce": True})
            
            if time.time() - start_scan > 20:
                self.log.emit("⚠️ CDP Scan lento")

            nodes = resp.get("nodes", [])
            elements = self._extract(nodes)
            selectors = self._ai_match(elements)
            self._save(selectors)

            self.log.emit(f"✅ Mapping completato: {len(selectors)} campi.")
            self.finished.emit(selectors)

        except Exception as e:
            self.log.emit(f"❌ Mapper error: {e}")
            self.finished.emit({})
        
        finally:
            if cdp:
                try: cdp.detach()
                except: pass

    def _auto_scroll(self, page):
        for _ in range(5):
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(1)

    def _extract(self, nodes):
        found = []
        for n in nodes:
            if self._is_interactive(n):
                css = self._css(n)
                if css:
                    found.append({
                        "tag": n.get("nodeName","").lower(),
                        "css": css,
                        "text": self._text(n),
                        "class": self._attr(n,"class")
                    })
        return found

    def _ai_match(self, elements):
        selectors = {}
        keys = {
            "stake_input": ["stake","importo","puntata","amount"],
            "place_button": ["scommetti","bet","place","gioca"],
            "login_button": ["login","accedi","entra"],
            "odds_value": ["quota","odd","price"],
            "search_box": ["search","cerca"]
        }
        for el in elements:
            fingerprint = (el["tag"]+" "+el["text"]+" "+el["class"]).lower()
            for field, words in keys.items():
                if field in selectors: continue
                if field=="stake_input" and el["tag"]!="input": continue
                if any(w in fingerprint for w in words):
                    selectors[field] = el["css"]
        return selectors

    def _save(self, selectors):
        if not selectors: return
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(os.path.join(CONFIG_DIR, "selectors_auto.yaml"), "w") as f:
            yaml.dump(selectors, f)

    def _attrs(self, n): return dict(zip(n.get("attributes",[])[::2], n.get("attributes",[])[1::2]))
    def _attr(self, n, k): return self._attrs(n).get(k, "")
    def _text(self, n): a=self._attrs(n); return a.get("aria-label","")+a.get("value","")
    def _is_interactive(self, n): 
        tag=n.get("nodeName","").upper()
        return tag in ["BUTTON","INPUT","A"] or "btn" in self._attr(n,"class")
    def _css(self, n):
        a=self._attrs(n); tag=n.get("nodeName","").lower()
        if "id" in a and not re.search(r'\d{5,}', a["id"]): return f"#{a['id']}"
        if "name" in a: return f"{tag}[name='{a['name']}']"
        return f"{tag}.{a['class'].split()[0]}" if "class" in a else None